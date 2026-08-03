import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";
import { requireProfile } from "@/lib/api";


export default async function WorkspaceLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const profile = await requireProfile();

  return (
    <div className="app-shell">
      <Sidebar
        role={profile.user.role}
      />
      <div className="workspace">
        <Topbar profile={profile} />
        <main className="workspace-content">
          {children}
        </main>
      </div>
    </div>
  );
}
