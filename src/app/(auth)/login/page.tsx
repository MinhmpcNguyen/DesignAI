"use client";

import { AppIcon, GoogleIcon } from "@/components/icons";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLogin } from "@/hooks/useAuth";

export default function LoginPage() {
  const router = useRouter();
  const login = useLogin();

  // NOTE: The email/password state and validation logic is purely for demonstration purposes.
  const [email, setEmail] = useState("test123@gmail.com");
  const [password, setPassword] = useState("test123");
  const [isFocused, setIsFocused] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [emailError, setEmailError] = useState("");
  const [apiError, setApiError] = useState("");

  const validateEmail = (value: string) => {
    const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    setEmailError(
      valid || value === "" ? "" : "Please enter a valid email address",
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setApiError("");
    login.mutate(
      { email, password },
      {
        onSuccess: () => router.push("/project"),
        onError: (err) => setApiError((err as Error).message),
      },
    );
  };

  return (
    <div className="w-full max-w-sm px-2 sm:px-0">
      {/* Heading */}
      <div className="flex justify-center mb-3 sm:mb-4">
        <AppIcon width={40} height={40} />
      </div>
      <h1 className="text-xl sm:text-2xl font-semibold text-center mb-1">
        Welcome to Auto Furniture
      </h1>
      <p className="text-sm text-center mb-5 sm:mb-8">
        Kindly fill in your details below to sign in
      </p>

      {/* OAuth button — Google login not supported yet */}
      <button
        disabled
        className="w-full flex font-semibold items-center justify-center gap-3 border border-[#CBCAD7] rounded-full py-2.5 text-sm mb-4 sm:mb-6 opacity-50 cursor-not-allowed"
      >
        Log in with Google
        <GoogleIcon />
      </button>

      {/* Divider */}
      <div className="flex items-center gap-3 mb-4 sm:mb-6">
        <div className="flex-1 h-px bg-current opacity-10" />
        <span className="text-xs opacity-40">Or</span>
        <div className="flex-1 h-px bg-current opacity-10" />
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="block text-sm" htmlFor="email">
            Email Address
          </label>
          <input
            id="email"
            type="email"
            placeholder="Enter your email address"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (emailError) validateEmail(e.target.value);
            }}
            onBlur={(e) => validateEmail(e.target.value)}
            required
            className={`w-full border rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-1 ${
              emailError
                ? "border-red-400 focus:ring-red-400"
                : "focus:ring-(--primary-color)"
            }`}
          />
          {emailError && (
            <p className="text-xs text-red-500 mt-1">{emailError}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <label className="block text-sm" htmlFor="password">
            Password
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full border rounded-lg pl-3 pr-15 py-2.5 text-sm outline-none focus:ring-1 focus:ring-(--primary-color)"
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
            />
            {isFocused && (
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-sm cursor-pointer"
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            )}
          </div>
        </div>

        {apiError && <p className="text-xs text-red-500">{apiError}</p>}

        <button
          type="submit"
          disabled={login.isPending}
          className="w-full flex items-center font-semibold border justify-center rounded-full py-3 mb-6 cursor-pointer mt-6 bg-(--primary-color) text-white hover:border-(--primary-color) hover:bg-transparent hover:text-(--primary-color) transition-colors duration-300 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {login.isPending ? "Logging in…" : "Login"}
        </button>
      </form>

      <p className="text-center text-sm mt-4">
        <a href="#" className="hover:underline">
          Forgot your password?
        </a>
      </p>

      <p className="text-center text-sm mt-2">
        Don&apos;t have an account?{" "}
        <Link
          href="/signup"
          className="font-semibold hover:underline text-(--primary-color)"
        >
          Sign up
        </Link>
      </p>
    </div>
  );
}
