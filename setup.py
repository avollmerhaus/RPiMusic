import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="RPiMusic",
    version="0.0.3",
    install_requires=['pika'],
    packages=setuptools.find_packages(),
    author="Aljoscha Vollmerhaus",
    author_email='pydev@aljoscha.vollmerhaus.net',
    description="Play URLs from AMQP messages via mpv",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/avollmerhaus/RPiMusic",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX :: Linux",
        "Environment :: Console"
    ],
    entry_points={
        'console_scripts': [ 'rpimusicd = RPiMusic.rpimusicd:rpimusicd', ],
    },
)