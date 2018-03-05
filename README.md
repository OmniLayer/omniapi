# omniapi
API Services for Omni 

<b>NOTE: The following is a work in progress and should not be considered production ready/usable</b>

## Install instructions
Follow nginx instructions to install nginx mainline branch 1.13.8 or greater
 - When done reference etc/nginx/sites-available/README for additional instructions

Follow instructions to make/install armory engine (https://github.com/goatpig/BitcoinArmory/blob/master/linuxbuild/Linux_build_notes.md)
 - (You may need to include/install the following additional tools: `sudo apt-get install autotools-dev autoconf libtool`)
Ensure "make install" installs armory into /usr/local/lib/armory 

Install python pip and the python packages from pip
 - sudo apt install python-pip
 - sudo pip install -r requirements.txt

## Config files needed
To connect to and use the omnicored client define the following file with the following structure.
```
cat ~/.bitcoin/bitcoin.conf
rpcuser=
rpcpassword=
rpcport=
rpcconnect=<ip address of host, only needed if not localhost>
```

To connect to the database define the following file with the following structure:
```
cat ~/.omni/sql.conf
sqluser=
sqlport=
sqlconnect=
sqldatabase=
sqlpassword=
```

Copy api/config.py.example to api/config.py and update it accordingly

## Running
Launch the api using `bash startApi.sh`
