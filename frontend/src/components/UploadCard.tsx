type Gate =
  | "ALLOWED"
  | "BLOCKED_NO_LICENSE"
  | "BLOCKED_REJECTED"
  | "BLOCKED_NEEDS_REVIEW"
  | "BLOCKED_LICENSE_EXPIRED"
  | "BLOCKED_SOURCE_RIGHTS";

export function UploadCard({
  title,
  gate = "BLOCKED_NO_LICENSE"
}: {
  title: string;
  gate?: Gate;
}) {
  const allowed = gate === "ALLOWED";
  const rejected = gate === "BLOCKED_REJECTED";
  return (
    <article className="card">
      <span className={`badge ${allowed ? "allowed" : "blocked"}`}>{gate}</span>
      <h3>{title}</h3>
      <div className="steps">
        {["메일발송", "회신", "승인", "대본", "영상초안", "private업로드", "공개가능여부"].map(
          (step) => <span className="badge" key={step}>{step}</span>
        )}
      </div>
      {rejected ? (
        <div className="steps"><button>폐기</button><button>무클립 전환</button></div>
      ) : (
        <div className="steps">
          <button disabled={!allowed}>공개예약</button>
          <button disabled={!allowed}>즉시공개</button>
        </div>
      )}
    </article>
  );
}
