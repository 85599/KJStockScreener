'''
 *  Project             :   KJScreener
 *  Author              :   Khushal Jain
 *  Created             :   05/05/2026
 *  Description         :   Class for handling OTA updates
'''

from classes.ColorText import colorText
from classes.Utility import isDocker, isGui
import requests
import os
import platform
import sys
import subprocess
import requests

class OTAUpdater:

    developmentVersion = 'd'

    # Download and replace exe through other process for Windows
    def updateForWindows(url):
        batFile = """@echo off
color a
echo [+] KJScreener Software Updater!
echo [+] Downloading Software Update...
echo [+] This may take some time as per your Internet Speed, Please Wait...
curl -o KJScreener.exe -L """ + url + """
echo [+] Newly downloaded file saved in %cd%
echo [+] Software Update Completed! Run'KJScreener.exe' again as usual to continue..
pause
del updater.bat & exit
        """
        f = open("updater.bat",'w')
        f.write(batFile)
        f.close()
        subprocess.Popen('start updater.bat', shell=True)
        sys.exit(0)

    # Download and replace bin through other process for Linux
    def updateForLinux(url):
        bashFile = """#!/bin/bash
echo ""
echo "[+] Starting KJScreener updater, Please Wait..."
sleep 3
echo "[+] KJScreener Software Updater!"
echo "[+] Downloading Software Update..."
echo "[+] This may take some time as per your Internet Speed, Please Wait..."
wget -q """ + url + """ -O KJScreener.bin
echo "[+] Newly downloaded file saved in $(pwd)"
chmod +x KJScreener.bin
echo "[+] Update Completed! Run 'KJScreener.bin' again as usual to continue.."
rm updater.sh
        """
        f = open("updater.sh",'w')
        f.write(bashFile)
        f.close()
        subprocess.Popen('bash updater.sh', shell=True)
        sys.exit(0)

        # Download and replace run through other process for Mac
    def updateForMac(url):
        bashFile = """#!/bin/bash
echo ""
echo "[+] Starting KJScreener updater, Please Wait..."
sleep 3
echo "[+] KJScreener Software Updater!"
echo "[+] Downloading Software Update..."
echo "[+] This may take some time as per your Internet Speed, Please Wait..."
curl -o KJScreener.run -L """ + url + """
echo "[+] Newly downloaded file saved in $(pwd)"
chmod +x KJScreener.run
echo "[+] Update Completed! Run 'KJScreener.run' again as usual to continue.."
rm updater.sh
        """
        f = open("updater.sh",'w')
        f.write(bashFile)
        f.close()
        subprocess.Popen('bash updater.sh', shell=True)
        sys.exit(0)

    # Parse changelog from release.md
    def showWhatsNew():
        url = "https://raw.githubusercontent.com/85599/KJStockScreener/main/src/release.md"
        md = requests.get(url)
        txt = md.text
        txt = txt.split("New?")[1]
        # txt = txt.split("## Downloads")[0]
        txt = txt.split("## Installation Guide")[0]
        txt = txt.replace('**','').replace('`','').strip()
        return (txt+"\n")

    @staticmethod
    def _parse_version(v: str):
        """Parse a semver string like '3.0.1' or 'v3.0.1' into a comparable tuple."""
        return tuple(int(x) for x in v.lstrip('v').split('.'))

    # Check for update and download if available
    def checkForUpdate(proxyServer, VERSION="1.0"):
        OTAUpdater.checkForUpdate.url = None
        guiUpdateMessage = ""
        try:
            resp = None
            now = OTAUpdater._parse_version(VERSION)
            if proxyServer:
                resp = requests.get("https://api.github.com/repos/85599/KJStockScreener/releases/latest",proxies={'https':proxyServer}, timeout=10)
            else:
                resp = requests.get("https://api.github.com/repos/85599/KJStockScreener/releases/latest", timeout=10)
            if resp.status_code != 200:
                raise Exception(f"GitHub API returned {resp.status_code}: {resp.json().get('message', 'Unknown error')}")
            # Disabling Exe check as Executables are deprecated v2.03 onwards
            '''
            if 'Windows' in platform.system():
                OTAUpdater.checkForUpdate.url = resp.json()['assets'][1]['browser_download_url']
                size = int(resp.json()['assets'][1]['size']/(1024*1024))
            elif 'Darwin' in platform.system():
                OTAUpdater.checkForUpdate.url = resp.json()['assets'][2]['browser_download_url']
                size = int(resp.json()['assets'][2]['size']/(1024*1024))
            else:
                OTAUpdater.checkForUpdate.url = resp.json()['assets'][0]['browser_download_url']
                size = int(resp.json()['assets'][0]['size']/(1024*1024))
            # if(float(resp.json()['tag_name']) > now):
            if(float(resp.json()['tag_name']) > now and not isDocker()):    # OTA not applicable if we're running in docker!
                print(colorText.BOLD + colorText.WARN + "[+] What's New in this Update?\n" + OTAUpdater.showWhatsNew() + colorText.END)
                action = str(input(colorText.BOLD + colorText.WARN + ('\n[+] New Software update (v%s) available. Download Now (Size: %dMB)? [Y/N]: ' % (str(resp.json()['tag_name']),size)))).lower()
                if(action == 'y'):
                    try:
                        if 'Windows' in platform.system():
                            OTAUpdater.updateForWindows(OTAUpdater.checkForUpdate.url)
                        elif 'Darwin' in platform.system():
                            OTAUpdater.updateForMac(OTAUpdater.checkForUpdate.url)
                        else:
                            OTAUpdater.updateForLinux(OTAUpdater.checkForUpdate.url)
                    except Exception as e:
                        print(colorText.BOLD + colorText.WARN + '[+] Error occured while updating!' + colorText.END)
                        raise(e)
            '''
            _tag = OTAUpdater._parse_version(resp.json()['tag_name'])
            if _tag > now and not isDocker():
                print(colorText.BOLD + colorText.FAIL + "[+] Executables are now DEPRECATED!\nFollow instructions given at https://github.com/85599/KJStockScreener to switch to Docker.\n" + colorText.END)
            elif _tag > now and isDocker():    # OTA not applicable if we're running in docker!
                print(colorText.BOLD + colorText.FAIL + ('\n[+] New Software update (v%s) available.\n[+] Run `docker pull callmejainsahab/KJScreener:latest` to update your docker to the latest version!\n' % (str(resp.json()['tag_name']))) + colorText.END)
                print(colorText.BOLD + colorText.WARN + "[+] What's New in this Update?\n" + OTAUpdater.showWhatsNew() + colorText.END)
                if isGui():
                    guiUpdateMessage = f"New Software update (v{resp.json()['tag_name']}) available - Watch this [**YouTube Video**](https://youtu.be/T41m13iMyJc) for additional help or Update by running following command:\n\n**`docker pull callmejainsahab/KJScreener:latest`**"
            elif _tag < now:
                # Local version is ahead of the tracked release repo (common for
                # forks / custom builds). Treat as normal release, not "dev mode",
                # so GUI does not show the red development banner or debug panels.
                _remote = str(resp.json()['tag_name']).lstrip('vV')
                print(colorText.BOLD + colorText.WARN + (
                    f"[+] Local version (v{VERSION}) is newer than remote "
                    f"(v{_remote}) — skipping OTA."
                ) + colorText.END)
                return None, guiUpdateMessage
        except Exception as e:
            # Rate-limit / network errors are non-fatal in GUI/Docker — just skip OTA
            err = str(e)
            if 'rate limit' in err.lower() or '403' in err:
                print(colorText.BOLD + colorText.WARN + "[+] OTA skipped (GitHub API rate limit). Continuing..." + colorText.END)
            else:
                print(colorText.BOLD + colorText.FAIL + "[+] Failure while checking update!" + colorText.END)
                print(e)
            if OTAUpdater.checkForUpdate.url != None:
                print(colorText.BOLD + colorText.BLUE + ("[+] Download update manually from %s\n" % OTAUpdater.checkForUpdate.url) + colorText.END)
        return None, guiUpdateMessage
