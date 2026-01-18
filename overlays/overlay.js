/**
 * Polymarket AI Show - Overlay Controller
 * 
 * This script manages the stream overlay UI, receiving updates via
 * WebSocket from the orchestrator to update market info, voting, etc.
 */

class OverlayController {
    constructor() {
        this.elements = {
            marketQuestion: document.getElementById('market-question'),
            marketOdds: document.getElementById('market-odds'),
            votingPanel: document.getElementById('voting-panel'),
            voteTimer: document.getElementById('vote-timer'),
            option1Name: document.getElementById('option-1-name'),
            option2Name: document.getElementById('option-2-name'),
            option1Fill: document.getElementById('option-1-fill'),
            option2Fill: document.getElementById('option-2-fill'),
            option1Count: document.getElementById('option-1-count'),
            option2Count: document.getElementById('option-2-count'),
            volume: document.getElementById('volume'),
            marketsCount: document.getElementById('markets-count'),
            totalVotes: document.getElementById('total-votes'),
            hostMaxLabel: document.getElementById('host-max-label'),
            hostBenLabel: document.getElementById('host-ben-label'),
        };
        
        this.ws = null;
        this.voteTimerInterval = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        
        this.init();
    }
    
    init() {
        console.log('🎬 Overlay controller initializing...');
        this.connectWebSocket();
        
        // Demo mode - show sample data
        this.showDemoData();
    }
    
    connectWebSocket() {
        // Connect to orchestrator's WebSocket server
        const wsUrl = 'ws://localhost:8765';  // Configure as needed
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('✅ Connected to orchestrator');
                this.reconnectAttempts = 0;
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };
            
            this.ws.onerror = (error) => {
                console.error('❌ WebSocket error:', error);
            };
            
            this.ws.onclose = () => {
                console.log('🔌 Disconnected from orchestrator');
                this.scheduleReconnect();
            };
        } catch (e) {
            console.log('WebSocket not available, running in demo mode');
        }
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
            console.log(`Reconnecting in ${delay}ms...`);
            setTimeout(() => this.connectWebSocket(), delay);
        }
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'market_update':
                this.updateMarket(data.market);
                break;
            case 'voting_start':
                this.startVoting(data.candidates, data.duration);
                break;
            case 'voting_update':
                this.updateVotes(data.tally, data.total);
                break;
            case 'voting_end':
                this.endVoting(data.winner);
                break;
            case 'speaker_change':
                this.updateSpeaker(data.speaker);
                break;
            case 'stats_update':
                this.updateStats(data.stats);
                break;
        }
    }
    
    updateMarket(market) {
        this.elements.marketQuestion.textContent = market.question;
        
        // Format odds
        const oddsText = Object.entries(market.odds)
            .map(([outcome, odds]) => `${outcome}: ${odds}`)
            .join(' | ');
        this.elements.marketOdds.textContent = oddsText;
        
        // Update volume
        if (market.volume) {
            this.elements.volume.textContent = market.volume;
        }
    }
    
    startVoting(candidates, duration) {
        this.elements.option1Name.textContent = candidates[0];
        this.elements.option2Name.textContent = candidates[1];
        this.elements.option1Fill.style.width = '50%';
        this.elements.option2Fill.style.width = '50%';
        this.elements.option1Count.textContent = '0 votes';
        this.elements.option2Count.textContent = '0 votes';
        
        // Show panel
        this.elements.votingPanel.style.display = 'block';
        this.elements.votingPanel.classList.add('show');
        
        // Start timer
        let remaining = duration;
        this.elements.voteTimer.textContent = remaining;
        
        this.voteTimerInterval = setInterval(() => {
            remaining--;
            this.elements.voteTimer.textContent = remaining;
            
            if (remaining <= 10) {
                this.elements.voteTimer.style.color = '#ff0000';
            }
            
            if (remaining <= 0) {
                clearInterval(this.voteTimerInterval);
            }
        }, 1000);
    }
    
    updateVotes(tally, total) {
        const votes1 = tally[1] || 0;
        const votes2 = tally[2] || 0;
        
        this.elements.option1Count.textContent = `${votes1} votes`;
        this.elements.option2Count.textContent = `${votes2} votes`;
        
        if (total > 0) {
            const pct1 = (votes1 / total) * 100;
            const pct2 = (votes2 / total) * 100;
            
            this.elements.option1Fill.style.width = `${pct1}%`;
            this.elements.option2Fill.style.width = `${pct2}%`;
        }
    }
    
    endVoting(winner) {
        clearInterval(this.voteTimerInterval);
        
        // Highlight winner
        if (winner === 1) {
            document.getElementById('option-1').style.background = 'rgba(0,255,136,0.2)';
        } else {
            document.getElementById('option-2').style.background = 'rgba(0,255,136,0.2)';
        }
        
        // Hide after delay
        setTimeout(() => {
            this.elements.votingPanel.style.display = 'none';
            this.elements.voteTimer.style.color = '#ff6b6b';
            document.getElementById('option-1').style.background = '';
            document.getElementById('option-2').style.background = '';
        }, 5000);
    }
    
    updateSpeaker(speaker) {
        // Remove speaking class from both
        this.elements.hostMaxLabel.classList.remove('speaking');
        this.elements.hostBenLabel.classList.remove('speaking');
        
        // Add to current speaker
        if (speaker === 'max') {
            this.elements.hostMaxLabel.classList.add('speaking');
        } else if (speaker === 'ben') {
            this.elements.hostBenLabel.classList.add('speaking');
        }
    }
    
    updateStats(stats) {
        if (stats.markets_discussed !== undefined) {
            this.elements.marketsCount.textContent = stats.markets_discussed;
        }
        if (stats.total_votes !== undefined) {
            this.elements.totalVotes.textContent = stats.total_votes;
        }
    }
    
    showDemoData() {
        // Show sample data for testing
        this.updateMarket({
            question: 'Will Bitcoin reach $100,000 by end of 2024?',
            odds: { 'Yes': '65%', 'No': '35%' },
            volume: '$2.5M'
        });
        
        this.elements.marketsCount.textContent = '3';
        this.elements.totalVotes.textContent = '142';
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.overlay = new OverlayController();
});
