import type {
  AuthenticatedProfile,
} from "@/lib/types";


export function Topbar({
  profile,
}: {
  profile: AuthenticatedProfile;
}) {
  return (
    <header className="topbar">
      <div>
        <div className="topbar-kicker">
          Accounts payable command center
        </div>
        <div className="topbar-environment">
          Local operations
          <span className="environment-dot">
            •
          </span>
          Live data
        </div>
      </div>

      <div className="topbar-actions">
        <div className="user-avatar">
          {profile.user.display_name
            .split(" ")
            .map((part) => part[0])
            .join("")
            .slice(0, 2)}
        </div>
        <div className="user-copy">
          <div className="user-name">
            {profile.user.display_name}
          </div>
          <div className="user-role">
            {profile.user.role.replaceAll(
              "_",
              " ",
            )}
          </div>
        </div>
        <form
          action="/api/auth/logout"
          method="post"
        >
          <button
            className="logout-button"
            type="submit"
          >
            Sign out
          </button>
        </form>
      </div>
    </header>
  );
}
