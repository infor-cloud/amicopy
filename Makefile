all: amicopy

clean:
	$(MAKE) -C tsunami-udp clean

amicopy: amicopy.py
	$(MAKE) -C tsunami-udp
	./insert_loadfile.py amicopy.py amicopy
	chmod +x amicopy
