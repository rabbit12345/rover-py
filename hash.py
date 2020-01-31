#!/usr/bin/python
# file hashing test
# download a remote file & compare with a local copy
# give up hexdeximal hash by SHA256
# version: 0.01
# modify date: 27/01/2020
# 
# 0.1
# 1. testing of file hashing function

import hashlib
import urllib
import requests
import subprocess

print(hashlib.algorithms_guaranteed)

def download_file(url):
	local_filename = "tmp." + url.split('/')[-1]
	# NOTE the stream=True parameter below
	with requests.get(url, stream=True) as r:
		r.raise_for_status()
		with open(local_filename, 'wb') as f:
			for chunk in r.iter_content(chunk_size=8192): 
				if chunk: # filter out keep-alive new chunks
					f.write(chunk)
					# f.flush()
	return local_filename

def dos2unix(filename):
  print("convert file to unix format")
  CMD("dos2unix " + filename)

def CMD(cmd):
  p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=False) 
  return (p.stdin, p.stdout, p.stderr) 

targetfile = "/home/core/rover.py" # Location of the file (can be set a different way)
BLOCK_SIZE = 512 # The size of each read from the file
dl_url = "https://raw.githubusercontent.com/rabbit12345/rover-py/master/rover.py"

file_hash1 = hashlib.sha256() # Create the hash object, can use something other than `.sha256()` if you wish
dos2unix(targetfile)
with open(targetfile, 'rb') as f: # Open the file to read it's bytes
  fb = f.read(BLOCK_SIZE) # Read from the file. Take in the amount declared above
  file_hash1.update(fb)

file_hash2 = hashlib.sha256()
http_stream = urllib.urlopen(dl_url)
update_file = http_stream.read(BLOCK_SIZE)
http_stream.close()
file_hash2.update(update_file)

print ('local file hash:  ' + file_hash1.hexdigest()) # Get the hexadecimal digest of the hash
print ('remote file hash: ' + file_hash2.hexdigest()) # Get the hexadecimal digest of the hash