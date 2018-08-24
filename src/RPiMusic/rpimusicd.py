#!/bin/env python3

import argparse
import logging
import signal
import sys
import os
import json
import subprocess
import pika
from time import sleep

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('RPiMusic')

class RPiMusic:
    STARTUP_TIMEOUT = 3
    PLAYER = '/usr/bin/mpv'
    PLAYER_ARGS = ['--no-terminal']

    def __init__(self, configfile):
        self.exit_flag = False
        self._amqp_channel = None
        self._parse_config(os.path.expanduser(configfile))
        self._url_cache_file = os.path.expanduser(self._url_cache_file)
        logger.info('fallback url set to %s', self._fallback_playlist_url)
        logger.info('trying to load last URL from %s', self._url_cache_file)
        try:
            with open(self._url_cache_file, 'r') as fh:
                jsondata = json.loads(fh.read())
                self._current_playlist_url = jsondata['playlisturl']
                logger.info('restored last url: %s', self._current_playlist_url)
        except (FileNotFoundError, KeyError):
            logger.info('unable to load URL, using fallback url')
            self._current_playlist_url = self._fallback_playlist_url

    def start(self):
        self._setup_amqp_queue()
        self._start_player()
        self._amqp_channel.start_consuming()

    def _setup_amqp_queue(self):
        queuename = 'RPiMusic_{}'.format(self._uuid)
        logger.info('registering queue %s', queuename)
        self._amqp_channel.queue_declare(queue=queuename, durable=True)
        self._amqp_channel.queue_bind(exchange='Xall', queue=queuename, routing_key=queuename)
        self._amqp_channel.queue_bind(exchange='Xall', queue=queuename, routing_key='RPiMusic_All')
        self._amqp_channel.basic_consume(self._handle_msg, queue=queuename)

    def _handle_msg(self, channel, method_frame, properties, body):
        logger.debug('msgid %d: got message', method_frame.delivery_tag)
        try:
            message = body.decode('utf-8')
            jsondata = json.loads(message)
            playlisturl = jsondata['playlisturl']
        except (KeyError, ValueError, AttributeError, TypeError):
            logger.error('msgid %d: handling error:', method_frame.delivery_tag, exc_info=True)
            channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=False)
        else:
            self._set_playlisturl(playlisturl)
            channel.basic_ack(delivery_tag=method_frame.delivery_tag)
            self._stop_player()
            self._start_player()

    def _start_player(self):
        args = [RPiMusic.PLAYER, ]
        args.extend(RPiMusic.PLAYER_ARGS)
        args.extend([self._current_playlist_url])
        logger.info('run %s', str(args))
        self._process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            retcode = self._process.wait(timeout=RPiMusic.STARTUP_TIMEOUT)
        except subprocess.TimeoutExpired:
            pass
        else:
            if self.exit_flag:
                pass
            else:
                logger.error('subprocess dead after %d seconds, assuming failure', RPiMusic.STARTUP_TIMEOUT)
                raise subprocess.CalledProcessError(retcode, cmd=args)

    def _set_playlisturl(self, playlisturl):
        with open(self._url_cache_file, 'w') as fh:
            content = {"playlisturl": playlisturl}
            fh.write(json.dumps(content))
        self._current_playlist_url = playlisturl

    def _stop_player(self):
        self._process.terminate()
        self._process.communicate()
        logger.info('stopped player')

    def _parse_config(self, configfile):
        with open(configfile, 'r') as fh:
            jsondata = json.loads(fh.read())
            self._amqp_url = jsondata['amqp_url']
            self._url_cache_file = jsondata['url_cache_file']
            self._fallback_playlist_url = jsondata['fallback_playlist_url']
            self._uuid = jsondata['uuid']

    def setup_amqp_connection(self):
        logger.info('connecting amqp')
        parameters = pika.URLParameters(self._amqp_url)
        parameters.ssl = True
        parameters.heartbeat = 60
        connection = pika.BlockingConnection(parameters=parameters)
        channel = connection.channel()
        channel.exchange_declare(exchange='Xall', exchange_type='direct')
        self._amqp_channel = channel

    def stop(self, *args):
        logger.info('stopping...')
        self.exit_flag = True
        try:
            self._amqp_channel.close()
        except (AttributeError, pika.exceptions.ConnectionClosed, pika.exceptions.ChannelClosed):
            pass

def rpimusicd():
    exitcode = 255
    try:
        parser = argparse.ArgumentParser(description='Play URLs from AMQP messages via mpv, cache URLs')
        parser.add_argument('--config', metavar='config', type=str, required=True, help='path to config file')
        parser.add_argument('--debug', dest='debug', action='store_true', required=False, default=False,
                            help='Activate debugging output')
        cliargs = parser.parse_args()

        if cliargs.debug:
            logger.setLevel(logging.DEBUG)
            logger.info('Loglevel set to DEBUG')

        worker = RPiMusic(cliargs.config)
        exitcode = 3

        while not worker.exit_flag:
            try:
                worker.setup_amqp_connection()
                signal.signal(signal.SIGTERM, worker.stop)
                signal.signal(signal.SIGINT, worker.stop)
                worker.start()
            except pika.exceptions.ConnectionClosed as err:
                logger.error('lost rabbitmq connection, reconnecting in 2s. reason: %s', str(err))
                sleep(5)
            except Exception as err:
                logger.error('caught fatal error: %s', err, exc_info=cliargs.debug)
                exitcode = 1
                worker.stop()
                break
            else:
                exitcode = 0
    finally:
        logging.shutdown()
        sys.exit(exitcode)

if __name__ == '__main__':
    rpimusicd()