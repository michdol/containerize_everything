import { combineReducers } from "redux";
import messages from './messages/reducer';


export enum EReduxActionTypes {
	APPEND_MESSAGE = "APPEND_MESSAGE",
	UPDATE_WORKER_INFO = "UPDATE_WORKER_INFO",
}

export interface IReduxBaseAction {
	type: EReduxActionTypes;
}

const rootReducer = combineReducers({
	messages,
});

export type AppState = ReturnType<typeof rootReducer>;

export default rootReducer;
