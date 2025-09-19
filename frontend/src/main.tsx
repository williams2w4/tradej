import React from "react";
import ReactDOM from "react-dom/client";
import { Provider } from "react-redux";
import { ConfigProvider } from "antd";

import App from "./App";
import { store } from "./store";

import "antd/dist/reset.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Provider store={store}>
      <ConfigProvider theme={{ token: { colorPrimary: "#1677ff" } }}>
        <App />
      </ConfigProvider>
    </Provider>
  </React.StrictMode>
);
