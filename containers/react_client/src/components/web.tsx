import * as React from "react";

import { w3cwebsocket as W3CWebSocket } from "websocket";

import { Address, WebSocketClient } from "../websocket_client/client";


interface IState {
	message: string;
}

export default class WebsocketClient extends React.Component<{}, IState> {
	private client: WebSocketClient;
	constructor(props: any) {
		super(props);
		const address = {host: "localhost", port: 8002};
		this.client = new WebSocketClient(address);
		this.debug_button = this.debug_button.bind(this);
		this.start_test_job = this.start_test_job.bind(this);
		this.authenticate = this.authenticate.bind(this);
		this.close = this.close.bind(this);
		this.updateMessage = this.updateMessage.bind(this);
		this.state = {
			message: ''
		}
	}

	componentDidMount() {
		this.client.connect();
		this.client.onopen(() => {
			console.log('Websocket client connected');
		})
		this.client.onmessage((message: any) => {
			console.log("Message", message);
		})
	}

	debug_button() {
		console.log("sending");
		let payload = JSON.stringify({
			"type": 3, // command
			"payload": this.state.message,
		})
		this.client.send(payload);
	}

	start_test_job() {
		console.log("sending");
		let payload = JSON.stringify({
			"type": 4, // command
			"payload": "test_job",
			"command": 1, // start job
			"args": {1: 2, 3: 4},
		})
		this.client.send(payload);
	}

	authenticate() {
		let payload = JSON.stringify({
			"type": 1, // auth
			"payload": "master"
		})
		this.client.send(payload)
	}

	close() {
		let payload = JSON.stringify({
			"type": 3, // auth
			"payload": "close"
		})
		this.client.send(payload)
	}

	updateMessage(e: any) {
		this.setState({message: e.target.value})
	}

	render() {
		return (
			<div>
				<div>
					<a onClick={this.debug_button}>send</a>
				</div>
				<div>
					<a onClick={this.start_test_job}>test_job</a>
				</div>
				<div>
					<input type="text" onChange={this.updateMessage} />
				</div>
				<div>
					<a onClick={this.authenticate}>auth</a>
				</div>
				<div>
					<a onClick={this.close}>close</a>
				</div>
			</div>
		)
	}
}