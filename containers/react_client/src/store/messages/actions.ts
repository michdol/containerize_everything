import { IMessage } from "./reducer";
import { EReduxActionTypes, IReduxBaseAction } from "../index";


export interface IReduxAppendMessageAction extends IReduxBaseAction {
	type: EReduxActionTypes.APPEND_MESSAGE;
	data: IMessage;
}

export interface IReduxUpdateWorkerInfoAction extends IReduxBaseAction {
	type: EReduxActionTypes.UPDATE_WORKER_INFO;
	data: IMessage;
}

export function addNewMessage(message: IMessage): IReduxAppendMessageAction {
	return {
		type: EReduxActionTypes.APPEND_MESSAGE,
		data: message
	}
}

export function updateWorkerInfo(message: IMessage): IReduxUpdateWorkerInfoAction {
	return {
		type: EReduxActionTypes.UPDATE_WORKER_INFO,
		data: message
	}
}