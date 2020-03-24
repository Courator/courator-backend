from setuptools import setup

setup(
    name='courator',
    version='0.1.0',
    description='An app to rate and suggest university courses',
    url='https://github.com/GIT_USER/courator',
    author='Matthew D. Scholefield',
    author_email='matthew331199@gmail.com',
    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='courator',
    packages=['courator'],
    install_requires=[],
    entry_points={
        'console_scripts': [
            'courator=courator.__main__:main'
        ],
    }
)