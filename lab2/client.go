package main

import (
	"fmt"
	"github.com/gorilla/websocket"
	"github.com/nsqio/go-nsq"
	"log"
	"math/rand"
	"net/http"
	"sync"
	"time"
	"encoding/json"
)

var (
	newline = []byte{'\n'}
	space   = []byte{' '}
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
}

type Handler struct {
	mutex sync.Mutex
	conn  *websocket.Conn
}

func (h *Handler) HandleMessage(m *nsq.Message) error {
	h.mutex.Lock()
	defer h.mutex.Unlock()
	return h.conn.WriteMessage(websocket.TextMessage, m.Body)
}

func wsHandler(cfg *nsq.Config) func(w http.ResponseWriter, r *http.Request) {
	return func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			log.Println(err)
			return
		}

		v, _ := json.MarshalIndent(cfg, "", "\t")
		log.Println(string(v))
		producer, err:= nsq.NewProducer("127.0.0.1:4150", cfg)
		if err != nil {
			log.Println(err)
			return
		}
		go func() {
			for {
				_, message, err := conn.ReadMessage()
				if err != nil {
					if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
						log.Printf("error: %v", err)
					}
					break
				}
				producer.Publish("test", message)
			}
		}()
		rand.Seed(time.Now().UnixNano())
		channel := fmt.Sprintf("client%06d#ephemeral", rand.Int()%999999)

		if consumer, err := nsq.NewConsumer("test", channel, cfg); err != nil {
			log.Println(err)
		} else {
			consumer.AddHandler(&Handler{conn: conn})
			err = consumer.ConnectToNSQLookupd(*nsqdHTTPAddrs)
			if err != nil {
				log.Fatal(err)
			}
		}
	}
}
