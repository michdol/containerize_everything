import * as React from "react";

import { w3cwebsocket as W3CWebSocket } from "websocket";

import { Address, WebSocketClient } from "../websocket_client/client";


export default class WebsocketClient extends React.Component {
	private client: WebSocketClient;
	constructor(props: any) {
		super(props);
		const address = {host: "localhost", port: 8002};
		this.client = new WebSocketClient(address);
		this.debug_button = this.debug_button.bind(this);
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
		this.client.send(JSON.stringify({"username": "react client"}));
	}

	render() {
		return (
			<div>
				Dupa
				<a onClick={this.debug_button}>send</a>
			</div>
		)
	}
}