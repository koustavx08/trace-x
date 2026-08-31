import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Compass } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-tracex-dark p-6">
      <Card className="max-w-md w-full">
        <CardContent className="p-8 flex flex-col items-center text-center gap-4">
          <div className="p-3 rounded-full bg-primary/10">
            <Compass className="w-8 h-8 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">404 - Page Not Found</h1>
            <p className="text-sm text-muted-foreground mt-2">
              The page you&apos;re looking for doesn&apos;t exist or has been moved.
            </p>
          </div>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center h-10 px-4 py-2 rounded-md font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Back to Dashboard
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
