"use client";

import Image from "next/image";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 overflow-hidden">
      {/* Left — static image panel */}
      <div className="hidden lg:block relative z-0">
        <Image
          src="/image/login-image.jpg"
          alt="Login image"
          fill
          className="object-cover"
        />
      </div>

      {/* Right — animated form panel */}
      <div className="flex items-center relative z-10 bg-white rounded-tl-2xl rounded-bl-2xl justify-center px-4 py-8 sm:px-8 sm:py-12 lg:py-16 overflow-hidden lg:-ml-6">
        {children}
      </div>
    </div>
  );
}
