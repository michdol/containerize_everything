import * as React from "react";

import WebsocketClient from "./web";

export interface IAppProps {}

export default function IApp(props: IAppProps) {
  return (
  	<div>
	  	<h1>Hello React Typescript!</h1>
	  	<WebsocketClient />
  	</div>
  );
}