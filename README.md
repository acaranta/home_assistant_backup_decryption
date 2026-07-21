# Home Assistant Backup Decryption Tool
## Intro
Since recent versions of Home Assistant, Backups are greatly imporved, automated and securely encrypted.
However, if, as an advanced user you wish to extract data from  these backup files, there is no simple way to do so.

This tool is  here to help you with data extraction.

## Input Files
What you will need : 
- one (or more) Automated Backup file
- your encryption key, or the backup emergency kit file

### Automated Backup file
To download this file you will have to :
- Go to your Home Assistant installation
- Then Navigate to `Settings->System->Backups`
- Select the Automated Backups list :
![Backup list](doc/img/SC-Automated_Backups_List.png)
- Finally, use the '...'  menu to download the file you require
![Bakcup File](doc/img/SC-Automated_Backups_Item-Download.png)

### Encryption Key
To get your encryption key, either you have (RECOMMENDED) stored it somewhere safe or :
- Go to your Home Assistant installation
- Then Navigate to `Settings->System->Backups->CONFIGURE BACKUP SETTINGS`
- Scroll down and you will find :
![Backup list](doc/img/SC-Encryption_key_get.png)
- From here either :
  - Use `Download emergency kit` to download your backup encryption emergency kit
  - use `Show my encryption key` to copy it and use it as is


## Run the Decryption tool
First you need to prepare your data :
Create data directories and copy files :
```
mkdir -p ./input ./output
cp Automatic_backup.*.tar ./input/
cp home_assistant_backup_emergency_kit*txt ./input/
```

### Directly from your terminal
This project uses [uv](https://docs.astral.sh/uv/) to manage its Python environment.
Requires **Python 3.11+** (uv will fetch a suitable interpreter for you if needed).

- Install uv, if you do not have it yet :
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```
- Get this repository :
```
git clone https://github.com/acaranta/home_assistant_backup_decryption.git
cd home_assistant_backup_decryption
```
- Run the script — uv creates the virtualenv and installs the locked dependencies on first
  run, so there is no separate install step :
```
uv run hass_backup_decrypt.py -i ./input -o ./output
```

### Using docker image
- You may build the image yourself :
```
docker build -t acaranta/home_assistant_backup_decryption .
```
- Or use the image built from this repository : [acaranta/home_assistant_backup_decryption](https://hub.docker.com/r/acaranta/home_assistant_backup_decryption)
- Then Run the image :
```
docker run --rm -ti \
    -v $(pwd)/input:/input:ro \
    -v $(pwd)/output:/output \
    --user=$(id -u):$(id -g) \
    acaranta/home_assistant_backup_decryption
```


## Help and Options
The script has several options available that you can review using 
```
uv run hass_backup_decrypt.py --help
# or
docker run --rm -ti acaranta/home_assistant_backup_decryption --help

🏠 Home Assistant Backup Decryption Tool
=======================================
usage: hass_backup_decrypt.py [-h] [-i INPUT] [-o OUTPUT] [-k KEY]

Home Assistant Backup Decryption Tool

options:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        Input directory containing backup files (default: /input)
  -o OUTPUT, --output OUTPUT
                        Output directory for decrypted files (default: /output)
  -k KEY, --key KEY     Encryption key (Format XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX)
```

NB : if the emergency kit is not found, and if you do not provide the encryption key as an option, you will be prompted to manually input it.

## Troubleshooting

- `SecureTarFile.__init__() got an unexpected keyword argument 'key'`
- `TarFile.extractall() got an unexpected keyword argument 'filter'`

Both were caused by running against dependency versions the script did not support
(see [issue #1](https://github.com/acaranta/home_assistant_backup_decryption/issues/1)),
and are fixed since version 0.2.0. The script now adapts to whichever
[securetar](https://pypi.org/project/securetar/) release is installed (the `key` argument
was renamed to `password` in securetar 2025.12.0), and only uses `extractall(filter=...)` on
Python versions that support it (3.12+, or the 3.11.4 / 3.10.12 backports — Debian 12 ships
Python 3.11.2, which does not). If you hit either message, update to the latest version.

## Development
Run the test suite with :
```
uv run pytest
```

## References :
The script idea comes from the script developped by [cogneato](https://github.com/cogneato/ha-decrypt-backup-tool) (idea and some part of the code).
But using as close as possible the same logic and modules (like [securetar](https://pypi.org/project/securetar/)) and keep as close as possible to the decryption methods used in [HA itself](https://github.com/home-assistant/core/blob/2121b943a32ebcbce7acb377cbf44c41d1805381/homeassistant/backup_restore.py#L92).