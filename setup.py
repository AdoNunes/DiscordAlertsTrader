import os
from setuptools import setup, find_packages
from pkg_resources import parse_requirements


# Read requirements from requirements.txt
with open('requirements.txt') as f:
    requirements = [str(req) for req in parse_requirements(f)]

# get the version
version = None
with open(os.path.join('DiscordAlertsTrader', '__init__.py'), 'r') as fid:
    for line in (line.strip() for line in fid):
        if line.startswith('__version__'):
            version = line.split('=')[1].strip().strip('\'')
            break

setup(
    name='DiscordAlertsTrader',
    version='1.0.0',
    author='Adonay Nunes',
    author_email='adonays.nunes@gmail.com',
    description='Package for automating discord stock and option alerts.',
    license='BSD (3-clause)',
    long_description='Listen to discord alerts, track profits, execute alerts in brokerage',
    url='',
    download_url='https://github.com/AdoNunes/DiscordAlertsTrader',
    packages=find_packages(),
    install_requires=requirements,
    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3.9',
        'Topic :: Communications :: Chat',
        'Topic :: Office/Business :: Financial',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Intended Audience :: Developers',
        'Intended Audience :: Financial and Insurance Industry',
        'Intended Audience :: Information Technology',
        'Operating System :: Microsoft :: Windows',
    ],
    entry_points = {'console_scripts': ['DiscordAlertsTrader = DiscordAlertsTrader.gui:gui'],
          }
)