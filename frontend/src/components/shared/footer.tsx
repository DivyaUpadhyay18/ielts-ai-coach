import Link from "next/link";
import { Zap, Github, Twitter, Linkedin, Mail } from "lucide-react";

const Footer = () => {
  const currentYear = new Date().getFullYear();

  const footerLinks = {
    product: [
      { name: "Writing Practice", href: "/writing" },
      { name: "Speaking Coach", href: "/speaking" },
      { name: "Pricing", href: "/#pricing" },
      { name: "Roadmap", href: "/#roadmap" },
    ],
    resources: [
      { name: "IELTS Tips", href: "/resources" },
      { name: "Band Descriptor", href: "/resources" },
      { name: "Success Stories", href: "/#reviews" },
      { name: "Support", href: "/contact" },
    ],
    legal: [
      { name: "Privacy Policy", href: "/privacy" },
      { name: "Terms of Service", href: "/terms" },
      { name: "Cookie Policy", href: "/cookies" },
    ],
  };

  return (
    <footer className="border-t border-border bg-background">
      <div className="container mx-auto px-4 py-12 md:py-16">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4 lg:grid-cols-5">
          
          {/* Brand Column */}
          <div className="col-span-2 lg:col-span-2">
            <Link href="/" className="flex items-center space-x-2 mb-4">
              <div className="flex h-7 w-7 items-center justify-center rounded bg-primary text-primary-foreground">
                <Zap className="h-4 w-4 fill-current" />
              </div>
              <span className="text-lg font-bold">IELTS<span className="text-accent">AI</span></span>
            </Link>
            <p className="text-sm text-muted-foreground max-w-xs mb-6">
              Empowering students worldwide to achieve their target band scores with personalized AI coaching and instant feedback.
            </p>
            <div className="flex space-x-4">
              <Twitter className="h-5 w-5 text-muted-foreground hover:text-primary cursor-pointer transition-colors" />
              <Github className="h-5 w-5 text-muted-foreground hover:text-primary cursor-pointer transition-colors" />
              <Linkedin className="h-5 w-5 text-muted-foreground hover:text-primary cursor-pointer transition-colors" />
            </div>
          </div>

          {/* Links Columns */}
          <div>
            <h3 className="text-sm font-semibold mb-4">Product</h3>
            <ul className="space-y-2">
              {footerLinks.product.map((link) => (
                <li key={link.name}>
                  <Link href={link.href} className="text-sm text-muted-foreground hover:text-primary transition-colors">
                    {link.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold mb-4">Resources</h3>
            <ul className="space-y-2">
              {footerLinks.resources.map((link) => (
                <li key={link.name}>
                  <Link href={link.href} className="text-sm text-muted-foreground hover:text-primary transition-colors">
                    {link.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold mb-4">Legal</h3>
            <ul className="space-y-2">
              {footerLinks.legal.map((link) => (
                <li key={link.name}>
                  <Link href={link.href} className="text-sm text-muted-foreground hover:text-primary transition-colors">
                    {link.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="mt-12 pt-8 border-t border-border flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-xs text-muted-foreground text-center md:text-left">
            © {currentYear} IELTS AI Coach. All rights reserved. IELTS is a registered trademark of University of Cambridge ESOL, the British Council, and IDP Education Australia.
          </p>
          <div className="flex items-center space-x-1 text-xs text-muted-foreground">
            <Mail className="h-3 w-3" />
            <span>contact@ieltsaicoach.com</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export { Footer };