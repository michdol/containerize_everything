var path = require('path');

import * as webpack from "webpack";
import * as HtmlWebPackPlugin from "html-webpack-plugin";

const htmlPlugin = new HtmlWebPackPlugin({
  template: "./src/index.html"
});

const config: webpack.Configuration = {
  mode: "development",
  entry: "./src/index.tsx",
  resolve: {
    // Add '.ts' and '.tsx' as resolvable extensions.
    extensions: [".ts", ".tsx", ".js", ".json"],
    // alias: {
    //   // Add the same to jest.config
    //   'src': path.resolve(__dirname, 'src/'),
    //   'components': path.resolve(__dirname, 'src/components/'),
    //   'store': path.resolve(__dirname, 'src/store/')
    // }
  },

  module: {
    rules: [
      // All files with a '.ts' or '.tsx' extension will be handled by 'awesome-typescript-loader'.
      { test: /\.tsx?$/, loader: "awesome-typescript-loader" }
    ]
  },
  plugins: [htmlPlugin]
};

export default config;