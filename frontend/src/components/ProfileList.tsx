import { ChevronRight, UserRound } from "lucide-react";
import type { Profile } from "../types/api";

type Props = {
  profiles: Profile[];
  selectedId: string | null;
  onSelect: (profile: Profile) => void;
};

function label(profile: Profile) {
  return String(profile.name || profile.full_name || profile.id);
}

function secondary(profile: Profile) {
  return String(profile.email || profile.phone || profile.location || profile._source?.filename || "No contact field");
}

export function ProfileList({ profiles, selectedId, onSelect }: Props) {
  return (
    <section className="panel profile-list">
      <div className="panel-heading">
        <h2>Profiles</h2>
        <span>{profiles.length} saved</span>
      </div>
      <div className="profile-scroll">
        {profiles.length === 0 ? <p className="empty">No profiles saved yet.</p> : null}
        {profiles.map((profile) => (
          <button
            className={`profile-row ${selectedId === profile.id ? "active" : ""}`}
            key={profile.id}
            onClick={() => onSelect(profile)}
            title={`Open ${label(profile)}`}
          >
            <UserRound size={20} />
            <span>
              <strong>{label(profile)}</strong>
              <small>{secondary(profile)}</small>
            </span>
            <ChevronRight size={18} />
          </button>
        ))}
      </div>
    </section>
  );
}
