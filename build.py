import geckoloader
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    longDescription = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as r:
    requires = [x for x in r]

setuptools.setup(
    name='GeckoLoader',
    version=geckoloader.__version__,    
    description='DOL Patcher for extending the codespace of Wii/GC games',
    long_description=longDescription,
    long_description_content_type="text/markdown",
    url='https://github.com/JoshuaMKW/geckoloader',
    author='JoshuaMK',
    author_email='joshuamkw2002@gmail.com',
    license='GNU General Public License v3.0',
    packages=setuptools.find_packages(),
    include_package_data=True,
    install_requires=requires,

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.8',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent'
    ],
    python_requires='>=3.8',
)