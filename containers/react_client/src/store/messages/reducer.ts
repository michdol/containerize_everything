import { EReduxActionTypes } from "../index";

import { IReduxAppendMessageAction, IReduxUpdateWorkerInfoAction } from "./actions";

export interface IMessage {
	id?: number;
	type: number;
	payload: any;
}

export interface IReduxMessagesState {
	messages: IMessage[];
	info: any;
}

const initialState: IReduxMessagesState = {
	messages: [],
	info: {},
}

type TMessagesReducerActions = 
	IReduxAppendMessageAction | IReduxUpdateWorkerInfoAction;


export default function(state: IReduxMessagesState = initialState, action: TMessagesReducerActions) {
	switch (action.type) {
		case EReduxActionTypes.APPEND_MESSAGE:
			let messagesCopy = Object.assign([], state.messages);
			messagesCopy.push(action.data);
			return {
				...state,
				messages: messagesCopy,
			};
		case EReduxActionTypes.UPDATE_WORKER_INFO:
			let infoCopy = Object.assign({}, state.info);
			infoCopy[action.data.payload.id] = action.data.payload;
			return {
				...state,
				info: infoCopy
			}
		default:
			return state;
	}
}