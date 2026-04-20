import { useState, cloneElement, isValidElement } from 'react'
import { Sidebar, MobileSidebar } from './Sidebar'
import TopBar from './TopBar'
import { motion, AnimatePresence } from 'framer-motion'
import { useSearchParams } from 'react-router-dom'

interface MainLayoutProps {
  children: React.ReactNode
}

export default function MainLayout({ children }: MainLayoutProps) {
  const [sidebarExpanded, setSidebarExpanded] = useState(true)
  const [searchParams, setSearchParams] = useSearchParams()
  const hubTab = searchParams.get('tab') || 'visao_geral'

  const setHubTab = (tab: string) => {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('tab', tab)
    setSearchParams(nextParams)
  }

  const childrenWithProps = isValidElement(children)
    ? cloneElement(children as React.ReactElement<any>, { 
        hubTab, 
        onHubTabChange: setHubTab 
      })
    : children

  return (
    <div className="flex min-h-screen bg-background selection:bg-primary/30 selection:text-white">
      {/* Desktop Sidebar */}
      <div className="hidden lg:block">
        <Sidebar 
          expanded={sidebarExpanded} 
          onToggle={() => setSidebarExpanded(!sidebarExpanded)} 
        />
      </div>

      <div className="flex flex-col flex-1 min-w-0">
        <TopBar 
          sidebarExpanded={sidebarExpanded} 
          hubTab={hubTab}
          onHubTabChange={setHubTab}
        />

        {/* Mobile menu trigger (TopBar handles some mobile stuff, but sidebar is handled by MobileSidebar) */}
        <div className="lg:hidden fixed top-0 left-0 h-14 flex items-center px-6 z-[60]">
          <MobileSidebar />
        </div>

        {/* Main Content Area */}
        <main 
          className="flex-1 transition-all duration-300 pt-14 pb-8"
          style={{ paddingLeft: sidebarExpanded ? '0' : '0' }} // Layout is relative to fixed sidebar
        >
          <div 
            className="transition-all duration-300 h-full"
            style={{ 
              marginLeft: sidebarExpanded ? '256px' : '72px' 
            }}
          >
            <AnimatePresence mode="wait">
              <motion.div
                key={window.location.pathname}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
                className="p-6 lg:p-10 max-w-[1600px] mx-auto min-h-full"
              >
                {childrenWithProps}
              </motion.div>
            </AnimatePresence>
          </div>
        </main>
      </div>

    </div>
  )
}
