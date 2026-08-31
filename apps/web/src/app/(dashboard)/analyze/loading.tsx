import { Card, CardContent, CardHeader } from "@/components/ui/card";

export default function Loading() {
  return (
    <div className="space-y-6 animate-pulse" role="status" aria-label="Loading">
      <div className="space-y-2">
        <div className="h-7 w-56 rounded-md bg-tracex-surface-hover" />
        <div className="h-4 w-80 rounded-md bg-tracex-surface-hover" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <div className="h-4 w-24 rounded bg-tracex-surface-hover" />
            </CardHeader>
            <CardContent>
              <div className="h-7 w-16 rounded bg-tracex-surface-hover" />
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardContent className="p-6 space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-4 w-full rounded bg-tracex-surface-hover" />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
