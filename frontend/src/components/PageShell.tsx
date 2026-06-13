export function PageShell({
  title,
  description,
  children
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <h1>{title}</h1>
      <p className="lead">{description}</p>
      {children}
    </>
  );
}
