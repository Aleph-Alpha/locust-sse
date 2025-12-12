package main

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/charmbracelet/fang"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/spf13/cobra"

	"github.com/locustio/locust-sse/tools/sse-server/pkg/server"
	"github.com/locustio/locust-sse/tools/sse-server/pkg/ui"
)

var (
	filePath string
	port     int
	endpoint string
	interval time.Duration
	headless bool
)

func main() {
	rootCmd := &cobra.Command{
		Use:   "sse-server",
		Short: "A configurable SSE server for E2E testing",
		RunE:  run,
	}

	rootCmd.Flags().StringVarP(&filePath, "file", "f", "", "Path to the input JSON file (required)")
	rootCmd.Flags().IntVarP(&port, "port", "p", 8080, "Port to listen on")
	rootCmd.Flags().StringVarP(&endpoint, "endpoint", "e", "/sse", "URL path to serve the stream on")
	rootCmd.Flags().DurationVarP(&interval, "interval", "i", 100*time.Millisecond, "Time to wait between sending events")
	rootCmd.Flags().BoolVar(&headless, "headless", false, "Run without TUI")

	rootCmd.MarkFlagRequired("file")

	if err := fang.Execute(context.Background(), rootCmd); err != nil {
		os.Exit(1)
	}
}

func run(cmd *cobra.Command, args []string) error {
	logCh := make(chan string, 100)

	cfg := server.Config{
		File:     filePath,
		Port:     port,
		Endpoint: endpoint,
		Interval: interval,
	}

	srv, err := server.NewServer(cfg, logCh)
	if err != nil {
		return err
	}

	// Start server in a goroutine
	go func() {
		if err := srv.Start(); err != nil {
			logCh <- fmt.Sprintf("Server error: %v", err)
			if headless {
				fmt.Printf("Server error: %v\n", err)
				os.Exit(1)
			}
		}
	}()

	if headless {
		// Just print logs to stdout
		fmt.Printf("Starting SSE server in headless mode on port %d...\n", port)
		for msg := range logCh {
			fmt.Println(msg)
		}
		return nil
	}

	// TUI mode
	configInfo := fmt.Sprintf("Port: %d | Endpoint: %s | Interval: %s | File: %s", port, endpoint, interval, filePath)
	p := tea.NewProgram(ui.NewModel(configInfo), tea.WithAltScreen())

	// Bridge logs to TUI
	go func() {
		for msg := range logCh {
			p.Send(ui.ServerMsg(msg))
		}
	}()

	if _, err := p.Run(); err != nil {
		return fmt.Errorf("error running TUI: %w", err)
	}

	return nil
}

