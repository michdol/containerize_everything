import { w3cwebsocket as W3CWebSocket } from "websocket";

export interface Address {
	host: string;
	port: number;
};


export class WebSocketClient {
	private client: any;
	address: Address;
	constructor(address: Address) {
		this.client = null;
		this.address = address;
		this.onmessage = this.onmessage.bind(this);
		this.onopen = this.onopen.bind(this);
		this.ping = this.ping.bind(this);
	}

	connect() {
		const address = `ws://${ this.address.host }:${ this.address.port }`;
		this.client = new W3CWebSocket(address);
	}

	onopen(callback: () => any) {
		this.client.onopen = () => {
			callback();
		}
	}

	onmessage(callback: (message: any) => any) {
		this.client.onmessage = (message: any) => {
			callback(message);
		}
	}

	send(message: string) {
		this.client.send(message);
	}

	ping() {
		this.client.ping(() => {console.log('pinged')})
	}
}