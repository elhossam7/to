import { Braces, CalendarClock, FileText } from "lucide-react";
import type { Profile } from "../types/api";

type Props = {
  profile: Profile | null;
};

const hiddenKeys = new Set(["id", "name", "full_name", "_id_strategy", "_source", "_warnings"]);

function profileTitle(profile: Profile) {
  return String(profile.personal?.full_name || profile.name || profile.full_name || profile.id);
}

function sourceLabel(profile: Profile) {
  if (profile._source?.files?.length) {
    return profile._source.files.map((file) => file.filename).filter(Boolean).join(", ");
  }
  return profile._source?.filename ?? "unknown source";
}

export function ProfileDetail({ profile }: Props) {
  if (!profile) {
    return (
      <section className="panel profile-detail empty-detail">
        <Braces size={34} />
        <p>Select a profile to inspect extracted fields.</p>
      </section>
    );
  }

  const fields = Object.entries(profile).filter(([key]) => !hiddenKeys.has(key));
  const title = profileTitle(profile);

  return (
    <section className="panel profile-detail">
      <div className="detail-title">
        <div>
          <h2>{title}</h2>
          <span>{profile.id}</span>
        </div>
        {profile._warnings?.length ? <strong className="warning">{profile._warnings.join(", ")}</strong> : null}
      </div>

      <div className="meta-grid">
        <div>
          <FileText size={18} />
          <span>{sourceLabel(profile)}</span>
        </div>
        <div>
          <CalendarClock size={18} />
          <span>{profile._source?.processed_at ?? "not processed"}</span>
        </div>
      </div>

      <div className="field-grid">
        {fields.map(([key, value]) => (
          <div className="field" key={key}>
            <span>{key.replaceAll("_", " ")}</span>
            <strong>{typeof value === "object" ? JSON.stringify(value, null, 2) : String(value)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
