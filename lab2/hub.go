package main

import "log"

type Hub struct {
	clients    map[*Client]bool
	broadcast  chan []byte
	register   chan *Client
	unregister chan *Client
}

func newHub() *Hub {
	return &Hub{
		broadcast:  make(chan []byte),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		clients:    make(map[*Client]bool),
	}
}

func (h *Hub) run() {
	for {
		select {
		case client := <-h.register:
			h.clients[client] = true
		case client := <-h.unregister:
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.incoming)
			} else {
				log.Println(client.addr, "doesn't exist anymore")
			}
		case message := <-h.broadcast:
			for client := range h.clients {
				select {
				case client.incoming <- message:
				default:
					close(client.incoming)
					delete(h.clients, client)
				}
			}
		}
	}
}
