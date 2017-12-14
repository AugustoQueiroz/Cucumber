#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import socket
import threading

class Socket:
	# Função Construtora
	def __init__ (self, host, port):
		# Define o endereço do socket
		self.host = host
		self.port = int(port)

		# Cria o socket propriamente dito
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.bind((host, port))

		# Começa desconectado
		self.peer = None
		self.connected = False

		# Define a próxima mensagem a ser enviada/recebida
		self.next_id = 0

	# Envia com o id da próxima mensagem esperada
	def sendack (self):
		self.sock.sendto("%d||ack" % (self.next_id), self.peer)


class ServerSocket(Socket):

	# Recebe a mensagem, Responde com o ack, e repassa a mensagem para o par se for a esperada
	def receiveandrespond (self):
		data, addr = self.sock.recvfrom(1024)
		data = data.split("||")
		mid = int(data[0])
		del data[0]
		m = "||".join(data)

		# Se estiver recebendo a primeira mensagem (estabelecimento de conexão), define o endereço recebido como seu par
		if mid == 0:
			self.peer = addr
			self.connected = True

		if addr != self.peer:
			# Se a mensagem não veio do seu par, responde dizendo que está ocupado
			self.sock.sendto("-1||busy", addr)
		elif mid < self.next_id:
			# Se veio do seu par, mas já havia sido recebida, reenvia o ack da próxima mensagem que está esperando
			self.sendack()
		elif mid == self.next_id:
			# Se veio do seu par e foi a mensagem esperada, envia o ack da próxima mensagem
			self.next_id += 1
			self.sendack()
			return m

		return None


class ClientSocket(Socket):
	# Especifico do socket cliente, mensagens que ainda não receberam ack
	waitingack = []

	# Função de Estabelescimento de Conexão
	def establishconnection (self, host, port):
		# Define o par como o endereço recebido
		self.peer = (host, port)

		# Envia um olá
		self.sock.sendto("0||olá", (host, port))

		# Define um timeout antes de reenviar
		self.sock.settimeout(2)

		# Enquanto não receber o ack reenvia
		while not self.connected:
			try:
				data, addr = self.sock.recvfrom(1024)
				data = data.split("||")
				mid = int(data[0])
				del data[0]
				m = "||".join(data)

				if mid == 1:
					self.connected = True
			except socket.timeout:
				self.sock.sendto("0||olá", (host, port))
				continue

	# Monta o "pacote" e envia
	def send (self, message):
		self.next_id += 1
		self.sock.sendto("%d||%s" % (self.next_id, message), self.peer)
		self.waitingack.append((self.next_id, message))

	# Checa se recebeu um ack
	def checkack (self):
		data, addr = self.sock.recvfrom(1024)
		data = data.split("||")
		mid = int(data[0])
		del data[0]
		m = "||".join(data)

		if addr == self.peer and m == 'ack' and mid >= self.waitingack[0][0]:
			# Se é um ack do par, e é para uma das mensagens esperando ack (ack cumulativo)
			for i, message in enumerate(self.waitingack):
				if message[0] <= mid:
					del self.waitingack[i]

	# Reenvia as mensagens que ainda não receberam ack
	def resend (self):
		for message in self.waitingack:
			self.sock.sendto(message, self.peer)


class Peer:
	# Função Construtora
	def __init__ (self, host, port):
		# Define o endereço do par
		self.host = host
		self.port = int(port)

		# Inicializa o par como vazio
		self.peer = None

		# Tenta inicializar os sockets de servidor e de cliente
		try:
			self.serversocket = ServerSocket(self.host, self.port)
		except socket.error:
			sys.stdout.write("Não foi possível criar o socket de servidor.\nProvavelmente a porta requerida (%d) já está em uso.\n" % (self.port))
			exit(1)
		try:
			self.clientsocket = ClientSocket(self.host, self.port+1)
		except socket.error:
			sys.stdout.write("Não foi possível criar o socket de cliente.\nProvavelmente a porta requerida (%d) já está em uso.\n" % (self.port))
			exit(1)

		# Variável de controle que diz se esse par deve ser desligado
		self.shutdown = False

	# Thread responsável pela parte "servidor"
	def serverside (self):
		self.serversocket.sock.setblocking(0)

		while not self.serversocket.connected:
			try:
				message = self.serversocket.receiveandrespond()
			except KeyboardInterrupt:
				self.serversocket.connected = True
				continue
			except:
				continue


		while self.serversocket.connected:
			try:
				message = self.serversocket.receiveandrespond()

				if message: # Se recebeu a mensagem em ordem, printa com um prompzinho
					sys.stdout.write("\033[F\033[KTHEM > %s\nMENSSAGE:\n" % message) # A maior parte do que tem aqui é só perfumaria
			except KeyboardInterrupt:
				self.serversocket.connected = False
				continue
			except:
				continue

	# Thread responsável pela parte "cliente"
	def clientside (self):
		self.clientsocket.sock.setblocking(0)

		while self.clientsocket.connected:
			try:
				self.clientsocket.checkack()
			except KeyboardInterrupt:
				self.clientsocket.connected = False
				continue
			except:
				# Se não tinha nenhum ack recebido, pega le outra mensagem para ser enviada
				message = raw_input("MENSSAGE:\n")
				sys.stdout.write("\033[F\033[K\033[F\033[KYOU  > %s\n" % message)
				self.clientsocket.send(message)

	# Inicia o par
	def startcommunication (self, host, port):
		self.server = threading.Thread(target=self.serverside)
		self.server.start()

		self.clientsocket.establishconnection(host, port)

		self.client = threading.Thread(target=self.clientside)
		self.client.start()

myhost = raw_input("My Host: ")
myport = int(raw_input("My Port: "))
peerhost = raw_input("Peer Host: ")
peerport = int(raw_input("Peer Port: "))

me = Peer(myhost, myport)
me.startcommunication(peerhost, peerport)