package main

import (
	"flag"
	"fmt"
	"github.com/nsqio/go-nsq"
	"log"
	"math/rand"
	"net/http"
	"time"
)

var (
	addr                   = flag.String("addr", ":8080", "http service address")
	nsqdLookupdHTTPAddress = flag.String("nsqd-lookupd-http-address", "127.0.0.1:4161", "nsqd-lookupd-tcp-address")
	nsqdTCPAddress         = flag.String("nsqd-tcp-address", "127.0.0.1:4150", "nsqd-tcp-address")
)

func serveHome(w http.ResponseWriter, r *http.Request) {
	log.Println(r.URL)
	if r.URL.Path != "/" {
		http.Error(w, "Not found", 404)
		return
	}
	if r.Method != "GET" {
		http.Error(w, "Method not allowed", 405)
		return
	}
	http.ServeFile(w, r, "home.html")
}

type nsqHandler struct {
	hub *Hub
}

func (h *nsqHandler) HandleMessage(m *nsq.Message) error {
	log.Println("Got", string(m.Body))
	select {
	case h.hub.broadcast <- m.Body:
		return nil
	default:
		return fmt.Errorf("cannot push message to hub")
	}
}

func main() {
	cfg := nsq.NewConfig()
	flag.Var(&nsq.ConfigFlag{cfg}, "consumer-opt", "option to passthrough to nsq.Consumer (may be given multiple times, http://godoc.org/github.com/nsqio/go-nsq#Config)")
	flag.Parse()

	producer, err := nsq.NewProducer(*nsqdTCPAddress, cfg)
	if err != nil {
		log.Println(err)
		return
	}

	for {
		if err := producer.Ping(); err != nil {
			log.Println(err)
			time.Sleep(time.Second)
			continue
		}
		break
	}

	rand.Seed(time.Now().UnixNano())
	channel := fmt.Sprintf("client%06d#ephemeral", rand.Int()%999999)
	hub := newHub()
	go hub.run()

	if consumer, err := nsq.NewConsumer("test", channel, cfg); err != nil {
		log.Println(err)
	} else {
		consumer.AddHandler(&nsqHandler{hub:hub})
		err = consumer.ConnectToNSQLookupd(*nsqdLookupdHTTPAddress)
		if err != nil {
			log.Fatal(err)
		}
	}

	http.HandleFunc("/", serveHome)
	http.HandleFunc("/ws", wsHandler(producer, hub))
	log.Printf("Serving on http://localhost%s/\n", *addr)
	if err := http.ListenAndServe(*addr, nil); err != nil {
		log.Fatal("ListenAndServe: ", err)
	}
}
