package main

import (
	"fmt"
	"github.com/gorilla/websocket"
	"github.com/nsqio/go-nsq"
	"log"
	"net/http"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
}

type Client struct {
	conn     *websocket.Conn
	addr     string
	incoming chan []byte
}

func wsHandler(producer *nsq.Producer, hub *Hub) func(w http.ResponseWriter, r *http.Request) {
	return func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			log.Println(err)
			return
		}
		defer conn.Close()

		client := Client{
			addr:     fmt.Sprint(conn.RemoteAddr()),
			conn:     conn,
			incoming: make(chan []byte, 256),
		}
		hub.register <- &client
		defer func(){hub.unregister <- &client}()

		go func() {
			defer func(){hub.unregister <- &client}()
			for {
				_, message, err := conn.ReadMessage()
				if err != nil {
					if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
						log.Printf("error: %v", err)
					}
					break
				}
				if err := producer.Publish("test", message); err != nil {
					log.Println(err)
					break
				}
			}
		}()

		for msg := range client.incoming {
			if err := conn.WriteMessage(websocket.TextMessage, msg); err != nil {
				log.Println(err)
				break
			}
		}
	}
}
