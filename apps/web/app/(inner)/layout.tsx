export default function InnerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="mx-auto min-h-screen w-full max-w-3xl px-4 pt-24 pb-16 sm:pt-28">
      {children}
    </div>
  );
}
