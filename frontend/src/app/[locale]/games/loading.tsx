export default function Loading() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8 animate-pulse">
        <div className="h-10 w-64 rounded bg-gray-200" />
        <div className="mt-4 h-5 w-96 rounded bg-gray-100" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="animate-pulse overflow-hidden rounded-lg border bg-white">
            <div className="aspect-[4/3] bg-gray-200" />
            <div className="p-3">
              <div className="h-4 w-3/4 rounded bg-gray-200" />
              <div className="mt-2 h-3 w-1/2 rounded bg-gray-100" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
