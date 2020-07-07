import * as React from "react";

import { w3cwebsocket as W3CWebSocket } from "websocket";


const client = new W3CWebSocket('ws://localhost:8002');

export default class WebsocketClient extends React.Component {
	componentDidMount() {
		client.onopen = () => {
			console.log('Websocket client connected');
			client.send(JSON.stringify({"username": "react client"}));
		};
		client.onmessage = (message) => {
			console.log("do I even")
			console.log(message);
		}
	}

	render() {
		return (
			<div>
				Dupa
			</div>
		)
	}
}