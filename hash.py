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

def downloadFile(url):
	print("download remote file from " + url)
	tmpFile = "tmp." + url.split('/')[-1]
	# NOTE the stream=True parameter below
	with requests.get(url, stream=True) as r:
		r.raise_for_status()
		with open(tmpFile, 'wb') as f:
			for chunk in r.iter_content(chunk_size=8192): 
				if chunk: # filter out keep-alive new chunks
					f.write(chunk)
					# f.flush()
	return tmpFile

def overwriteFile(localFile, tmpFile):
	print("over write " + localFile + " with " + tmpFile)
	CMD("cp " + tmpFile + " " + localFile)
	CMD("rm " + tmpFile)

def dos2unix(filename):
  print("convert file to unix format")
  CMD("dos2unix " + filename)

def CMD(cmd):
  p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=False) 
  return (p.stdin, p.stdout, p.stderr) 

def hashSHA256(fileobject):
	hashing = hashlib.sha256()
	hashing.update(fileobject)
	return hashing.hexdigest()

def checkHash(targetFile, serverurl):
	# check hash value of loca file 1 vs remote file 2
	
	# treat local file : convert to unix format
	dos2unix(targetFile)
	with open(targetFile, 'rb') as f: # Open the file to read it's bytes
		fb = f.read(BLOCK_SIZE) # Read from the file. Take in the amount declared above  
	localhexdigest = hashSHA256(fb)

  # download remove file  
	http_stream = urllib.urlopen(serverurl)
	update_file = http_stream.read(BLOCK_SIZE)
	http_stream.close()
	remotehexdigest = hashSHA256(update_file)

	if localhexdigest == remotehexdigest:
		samefile = 1
		print("file version is the same")
	else:
		samefile = 0
		print("file version is different")

	print ('local file hash:  ' + localhexdigest) # Get the hexadecimal digest of the hash
	print ('remote file hash: ' + remotehexdigest) # Get the hexadecimal digest of the hash

	return samefile

def updatecode(targetFile, serverurl):
	# check hash
	# if not same : download remote file in full into tmp file
	# then overwrite local file
	if checkHash(targetFile, serverurl) == 0:
		tmpFile = downloadFile(serverurl)
		overwriteFile(targetFile, tmpFile)


BLOCK_SIZE = 512 # The size of each read from the file
serverurl = "https://raw.githubusercontent.com/rabbit12345/rover-py/master/rover.py"
targetFile = "/home/core/" + serverurl.split('/')[-1] # Location of the file (can be set a different way)
tmpFile = ""

updatecode(targetFile, serverurl)
