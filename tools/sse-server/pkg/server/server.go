package server

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"
)

// Config holds the server configuration.
type Config struct {
	File     string
	Port     int
	Endpoint string
	Interval time.Duration
}

// Server represents the SSE server.
type Server struct {
	Config Config
	Events []interface{}
	LogCh  chan<- string
}

// NewServer creates a new SSE server.
func NewServer(cfg Config, logCh chan<- string) (*Server, error) {
	content, err := os.ReadFile(cfg.File)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	var events []interface{}
	if err := json.Unmarshal(content, &events); err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w", err)
	}

	return &Server{
		Config: cfg,
		Events: events,
		LogCh:  logCh,
	}, nil
}

// Start starts the HTTP server.
func (s *Server) Start() error {
	mux := http.NewServeMux()
	mux.HandleFunc(s.Config.Endpoint, s.handleSSE)

	addr := fmt.Sprintf(":%d", s.Config.Port)
	s.log(fmt.Sprintf("Server listening on http://localhost%s%s", addr, s.Config.Endpoint))

	return http.ListenAndServe(addr, mux)
}

func (s *Server) handleSSE(w http.ResponseWriter, r *http.Request) {
	// Set CORS headers
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

	if r.Method == "OPTIONS" {
		return
	}

	// Set SSE headers
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming not supported", http.StatusInternalServerError)
		return
	}

	clientAddr := r.RemoteAddr
	s.log(fmt.Sprintf("Client connected: %s", clientAddr))

	ctx := r.Context()

	for i, event := range s.Events {
		select {
		case <-ctx.Done():
			s.log(fmt.Sprintf("Client disconnected: %s", clientAddr))
			return
		default:
			data, err := json.Marshal(event)
			if err != nil {
				s.log(fmt.Sprintf("Error marshaling event %d: %v", i, err))
				continue
			}

			fmt.Fprintf(w, "data: %s\n\n", data)
			flusher.Flush()
			
			s.log(fmt.Sprintf("Sent event %d to %s", i+1, clientAddr))
			time.Sleep(s.Config.Interval)
		}
	}

	// Keep connection open until client disconnects or we want to close it explicitly.
	// For this test server, we just wait for the client to go away after sending all events
	// if we don't loop. The plan didn't strictly specify looping, but usually test servers
	// might just finish. However, to keep the connection open (as SSE often does), we wait.
	<-ctx.Done()
	s.log(fmt.Sprintf("Client disconnected after completion: %s", clientAddr))
}

func (s *Server) log(msg string) {
	if s.LogCh != nil {
		s.LogCh <- msg
	} else {
		fmt.Println(msg)
	}
}

