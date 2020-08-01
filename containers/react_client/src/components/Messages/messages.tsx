import * as React from "react";
import { AnyAction, bindActionCreators, Dispatch } from 'redux';
import { connect } from 'react-redux';

import { AppState } from "../../store/index";


const mapStateToProps = (state: AppState) => ({
	messages: state.messages.messages,
});

type TMessagesComponentProps = ReturnType<typeof mapStateToProps>;

class MessagesComponent extends React.Component<TMessagesComponentProps, {}> {
	renderMessages() {
		const messages = this.props.messages;
		console.log("MESSAGES", messages);
		return messages.map((message, idx) => {
			const payload = JSON.stringify(message.payload);
			return <li key={idx}>
				Type: { message.type } - { payload }
			</li>
		})
	}

	render() {
		return (
			<div>
				<div>Messages component</div>
				<div>
					<ul>
						{ this.renderMessages() }
					</ul>
				</div>
			</div>
		)
	}
}


export default connect(mapStateToProps)(MessagesComponent);