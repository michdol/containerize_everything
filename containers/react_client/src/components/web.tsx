import * as React from "react";
import { AnyAction, bindActionCreators, Dispatch } from "redux";
import { connect } from "react-redux";

import { w3cwebsocket as W3CWebSocket } from "websocket";

import { Address, WebSocketClient } from "../websocket_client/client";
import MessagesComponent from "./Messages/messages";
import { addNewMessage, updateWorkerInfo } from "../store/messages/actions";


interface IState {
	message: string;
};

const mapDispatchToProps = (dispatch: Dispatch<AnyAction>) =>
	bindActionCreators({
		addNewMessage,
		updateWorkerInfo,
	}, dispatch
);

type TWebsocketClientProps = ReturnType<typeof mapDispatchToProps>;

class WebsocketClientComponent extends React.Component<TWebsocketClientProps, IState> {
	private client: WebSocketClient;
	constructor(props: any) {
		super(props);
		const address = {host: "localhost", port: 8002};
		this.client = new WebSocketClient(address);
		this.debug_button = this.debug_button.bind(this);
		this.start_test_job = this.start_test_job.bind(this);
		this.start_word_counter= this.start_word_counter.bind(this);
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
			// console.log("Message", message);
			let data = JSON.parse(message.data);
			// console.log("Message type: ", data.type, "payload: ", data.payload);
			if (data.type === 2) {
				this.props.updateWorkerInfo(data);
			} else {
				this.props.addNewMessage(data);
			}
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
			"name": "test_job",
			"command": 1, // start job
			"args": {1: 2, 3: 4},
		})
		this.client.send(payload);
	}

	start_word_counter() {
		console.log("sending");
		let payload = JSON.stringify({
			"type": 4, // command
			"name": "word_counter",
			"command": 1, // start job
			"args": {
				"url": [
					"https://www.bbc.com",
					"https://news.yahoo.com/",
					"https://www.huffpost.com/",
					"https://news.google.com/topstories",
				],
				"word": "coronavirus",
				"required_workers": 4,
			},
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
				<MessagesComponent />
				<div>
					<a onClick={this.debug_button}>send</a>
				</div>
				<div>
					<a onClick={this.start_test_job}>test_job</a>
				</div>
				<div>
					<a onClick={this.start_word_counter}>word_counter</a>
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

export default connect(null, mapDispatchToProps)(WebsocketClientComponent);