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
		// JSON.stringify({"username": "react client"})
		this.client.send(this.state.message);
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
					<input type="text" onChange={this.updateMessage} />
				</div>
			</div>
		)
	}
}