import React from "react";
import { Link, useLocation } from "react-router-dom";
import { createPageUrl } from "@/utils";
import { ClipboardList, FileText, ClipboardCheck, Bot, Menu, Package, PlayCircle, Sparkles, LogOut, User, Shield } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarHeader,
  SidebarProvider,
  SidebarTrigger,
  SidebarFooter,
} from "@/components/ui/sidebar";
import DemoOverlay from "@/components/DemoOverlay";
import { useAuth } from "@/lib/AuthContext";

const navigationItems = [
  {
    title: "Test Plan",
    url: createPageUrl("TestPlan"),
    icon: ClipboardList,
  },
  {
    title: "AI Insights",
    url: createPageUrl("AIInsights"),
    icon: Sparkles,
  },
  {
    title: "Releases",
    url: createPageUrl("Releases"),
    icon: Package,
  },
  {
    title: "TOAB/RK/IA",
    url: createPageUrl("toab-rk-ia"),
    icon: FileText,
  },
  {
    title: "Requirements",
    url: createPageUrl("Requirements"),
    icon: FileText,
  },
  {
    title: "Test Cases",
    url: createPageUrl("TestCases"),
    icon: ClipboardCheck,
  },
  {
    title: "Testcase Migration",
    url: createPageUrl("testcase-migration"),
    icon: ClipboardCheck,
  },
  {
    title: "Automations",
    url: createPageUrl("Automations"),
    icon: Bot,
  },
  {
    title: "Executions",
    url: createPageUrl("Executions"),
    icon: PlayCircle,
  },
];

export default function Layout({ children }) {
  const location = useLocation();
  const { user, logout, authEnabled } = useAuth();

  const userRole = user?.role || 'viewer';
  const isAdmin = userRole === 'admin';

  const roleBadgeColors = {
    admin: 'bg-red-100 text-red-700',
    editor: 'bg-amber-100 text-amber-700',
    viewer: 'bg-slate-100 text-slate-600',
  };

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-gradient-to-br from-slate-50 to-blue-50">
        <DemoOverlay />
        <Sidebar className="border-r border-slate-200 bg-white">
          <SidebarHeader className="border-b border-slate-200 p-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl flex items-center justify-center shadow-lg">
                <ClipboardCheck className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="font-bold text-lg text-slate-900">TestMaster</h2>
                <p className="text-xs text-slate-500">QA Management</p>
              </div>
            </div>
          </SidebarHeader>
          
          <SidebarContent className="p-3">
            <SidebarGroup>
              <SidebarGroupLabel className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-3 py-2">
                Navigation
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {navigationItems.map((item) => (
                    <SidebarMenuItem key={item.title}>
                      <SidebarMenuButton 
                        asChild 
                        className={`hover:bg-blue-50 hover:text-blue-700 transition-all duration-200 rounded-lg mb-1 ${
                          location.pathname === item.url ? 'bg-blue-50 text-blue-700 font-medium' : ''
                        }`}
                      >
                        <Link to={item.url} className="flex items-center gap-3 px-3 py-2.5">
                          <item.icon className="w-5 h-5" />
                          <span>{item.title}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>

          <SidebarFooter className="border-t border-slate-200 p-3">
            <SidebarMenu>
              {/* Admin link — only shown to admin role */}
              {isAdmin && (
                <SidebarMenuItem>
                  <SidebarMenuButton
                    asChild
                    className={`hover:bg-blue-50 hover:text-blue-700 transition-all duration-200 rounded-lg ${
                      location.pathname === createPageUrl('admin') ? 'bg-blue-50 text-blue-700 font-medium' : ''
                    }`}
                  >
                    <Link to={createPageUrl('admin')} className="flex items-center gap-3 px-3 py-2.5">
                      <Shield className="w-4 h-4" />
                      <span>Admin</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )}
            </SidebarMenu>

            {/* User info & logout */}
            {user && (
              <div className="mt-2 px-3 py-3 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                    <User className="w-4 h-4 text-blue-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 truncate">{user.name || user.username}</p>
                    <div className="flex items-center gap-1.5">
                      <span className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded-full ${roleBadgeColors[userRole] || roleBadgeColors.viewer}`}>
                        {userRole}
                      </span>
                    </div>
                  </div>
                </div>
                {authEnabled && (
                  <button
                    onClick={logout}
                    className="w-full flex items-center justify-center gap-2 text-xs text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-md py-1.5 transition-colors"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    Sign out
                  </button>
                )}
              </div>
            )}
          </SidebarFooter>
        </Sidebar>

        <main className="flex-1 flex flex-col">
          <header className="bg-white/80 backdrop-blur-sm border-b border-slate-200 px-6 py-4 lg:hidden sticky top-0 z-10">
            <div className="flex items-center gap-4">
              <SidebarTrigger>
                <Menu className="w-6 h-6" />
              </SidebarTrigger>
              <h1 className="text-xl font-bold text-slate-900">TestMaster</h1>
            </div>
          </header>

          <div className="flex-1 overflow-auto">
            {children}
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}