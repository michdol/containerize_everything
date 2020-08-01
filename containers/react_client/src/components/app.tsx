import * as React from "react";
import { applyMiddleware, createStore } from "redux";
import { Provider } from "react-redux";
import logger, { createLogger } from "redux-logger";

import WebsocketClient from "./web";
import rootReducer, { EReduxActionTypes } from "../store/index";


const logger_ = createLogger({
	predicate: (getState, action) => action.type !== EReduxActionTypes.UPDATE_WORKER_INFO
});

const store = createStore(
	rootReducer,
	applyMiddleware(logger_)
)

export interface IAppProps {}

export default function IApp(props: IAppProps) {
  return (
  	<div>
	  	<h1>Hello React Typescript!</h1>
	  	<Provider store={store}>
	  		<WebsocketClient />
	  	</Provider>
  	</div>
  );
}