import AuthGuard from "@/components/AuthGuard";
import MainHeader from "@/components/layout/main/MainHeader";
import MainSidebar from "@/components/layout/main/MainSidebar";

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <div className="h-screen flex flex-col">
        {/* Header */}
        <div className="shrink-0" style={{ border: "var(--border-style)" }}>
          <MainHeader />
        </div>

        {/* Body */}
        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar (icon-only) */}
          <div
            className="shrink-0"
            style={{ borderRight: "var(--border-style)" }}
          >
            <MainSidebar />
          </div>

          {/* Main content */}
          <main className="flex-1 overflow-y-auto py-4 px-0 lg:px-10">
            {children}
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
