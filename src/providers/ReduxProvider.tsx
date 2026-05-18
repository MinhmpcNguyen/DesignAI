"use client";

import { Provider } from "react-redux";
import { ReactNode, useEffect } from "react";
import { store } from "@/states/store";
import { authActions } from "@/states/slices/auth/state";
import { setAuthCookie, clearAuthCookie } from "@/lib/authCookie";

function AuthHydrator() {
  useEffect(() => {
    store.dispatch(authActions.initAuth());
    const { accessToken } = store.getState().auth;
    if (accessToken) {
      setAuthCookie();
    } else {
      clearAuthCookie();
    }
  }, []);
  return null;
}

export default function ReduxProvider({ children }: { children: ReactNode }) {
  return (
    <Provider store={store}>
      <AuthHydrator />
      {children}
    </Provider>
  );
}
