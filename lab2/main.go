package main

import (
	"flag"
	"github.com/nsqio/go-nsq"
	"log"
	"net/http"
)

var (
	addr          = flag.String("addr", ":8080", "http service address")
	nsqdHTTPAddrs = flag.String("nsqd-http-address", "", "nsqd-http-adress")
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

func main() {
	cfg := nsq.NewConfig()
	flag.Var(&nsq.ConfigFlag{cfg}, "consumer-opt", "option to passthrough to nsq.Consumer (may be given multiple times, http://godoc.org/github.com/nsqio/go-nsq#Config)")
	flag.Parse()

	if len(*nsqdHTTPAddrs) == 0 {
		log.Fatal("--nsqd-http-address required")
	}

	http.HandleFunc("/", serveHome)
	http.HandleFunc("/ws", wsHandler(cfg))
	log.Printf("Serving on http://localhost%s/\n", *addr)
	if err := http.ListenAndServe(*addr, nil); err != nil {
		log.Fatal("ListenAndServe: ", err)
	}
}
