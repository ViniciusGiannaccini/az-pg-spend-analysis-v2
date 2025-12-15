import Head from 'next/head'
import { useRouter } from 'next/router'
import Image from 'next/image'
import React from 'react'

export default function Home() {
    const router = useRouter()

    const handleTaxonomyClick = () => {
        router.push('/taxonomy')
    }

    return (
        <React.Fragment>
            <Head>
                <title>Procurement Garage - Spend Analysis Agent</title>
                <meta name="description" content="AI-Powered Spend Analysis Platform" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
            </Head>

            <main className="min-h-screen bg-gradient-to-br from-[#0e0330] via-[#1c0957] to-[#0e0330] relative overflow-hidden">
                {/* Background Elements - PG Style */}
                <div className="absolute inset-0 overflow-hidden">
                    {/* Gradient Orbs matching PG brand */}
                    <div className="absolute top-[-150px] right-[-100px] w-[500px] h-[500px] bg-gradient-to-br from-primary-600/20 to-primary-500/10 rounded-full blur-3xl" />
                    <div className="absolute bottom-[-100px] left-[-50px] w-[400px] h-[400px] bg-gradient-to-tr from-primary-500/15 to-primary-600/10 rounded-full blur-3xl" />
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-gradient-to-r from-primary-600/5 to-primary-500/5 rounded-full blur-3xl" />

                    {/* Subtle Grid Pattern */}
                    <div
                        className="absolute inset-0 opacity-[0.03]"
                        style={{
                            backgroundImage: `radial-gradient(circle at 1px 1px, rgba(255,255,255,0.3) 1px, transparent 0)`,
                            backgroundSize: '50px 50px'
                        }}
                    />

                    {/* Top Accent Line */}
                    <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-primary-500 to-transparent opacity-50" />
                </div>

                {/* Content */}
                <div className="relative z-10 min-h-screen flex flex-col items-center justify-center p-8">
                    <div className="max-w-5xl w-full">
                        {/* Logo & Header */}
                        <div className="text-center mb-8 animate-fadeIn">
                            <div className="inline-block mb-8">
                                <Image
                                    src="/pg-logo.png"
                                    alt="Procurement Garage"
                                    width={350}
                                    height={70}
                                    priority
                                    className="w-auto h-14 md:h-16"
                                />
                            </div>

                            {/* Title */}
                            <h1 className="text-2xl md:text-4xl font-light text-white/90 mb-4 tracking-tight">
                                Spend Analysis{' '}
                                <span className="relative inline-block">
                                    <span className="font-bold bg-gradient-to-r from-primary-300 to-primary-100 bg-clip-text text-transparent">AI Agent</span>
                                    <span className="absolute -bottom-1 left-0 right-0 h-0.5 bg-gradient-to-r from-primary-300 to-primary-100 rounded-full" />
                                </span>
                            </h1>

                            <p className="text-base md:text-lg text-white/60 max-w-xl mx-auto leading-relaxed">
                                Transforme seus dados de gastos em insights estratégicos com inteligência artificial
                            </p>

                            {/* Version Badge */}
                            <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 bg-white/10 backdrop-blur-sm rounded-full border border-white/10">
                                <div className="w-1.5 h-1.5 rounded-full bg-primary-500 animate-pulse" />
                                <span className="text-xs text-white/70 font-medium">v1.0 Beta</span>
                            </div>
                        </div>

                        {/* Cards Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
                            {/* Card 1: Realizar Taxonomia - Active */}
                            <button
                                onClick={handleTaxonomyClick}
                                className="group bg-white/10 backdrop-blur-md rounded-2xl border border-white/10 text-left p-6 transition-all duration-500 hover:bg-white/15 hover:border-primary-500/50 hover:shadow-[0_8px_40px_rgba(98,74,186,0.2)] hover:translate-y-[-4px] relative overflow-hidden"
                            >
                                {/* Hover Glow */}
                                <div className="absolute inset-0 bg-gradient-to-br from-primary-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-2xl" />

                                {/* Icon */}
                                <div className="relative mb-4 inline-flex p-3 rounded-xl bg-gradient-to-br from-primary-600 to-primary-500 shadow-lg group-hover:shadow-[0_8px_30px_rgba(98,74,186,0.4)] transition-all duration-500 group-hover:scale-110">
                                    <svg
                                        xmlns="http://www.w3.org/2000/svg"
                                        fill="none"
                                        viewBox="0 0 24 24"
                                        strokeWidth={2}
                                        stroke="white"
                                        className="w-6 h-6"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
                                        />
                                    </svg>
                                </div>

                                <h2 className="relative text-xl font-bold text-white mb-2 group-hover:text-primary-400 transition-colors">
                                    Realizar Taxonomia
                                </h2>
                                <p className="relative text-white/60 leading-relaxed mb-5">
                                    Estruture e organize sua base de gastos por setor usando IA
                                </p>

                                {/* Features List */}
                                <ul className="relative text-sm text-white/50 space-y-2.5 mb-6">
                                    <li className="flex items-center gap-2.5">
                                        <div className="w-5 h-5 rounded-full bg-primary-500/20 flex items-center justify-center group-hover:bg-primary-500/30 transition-colors">
                                            <svg className="w-3 h-3 text-primary-400" fill="currentColor" viewBox="0 0 20 20">
                                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                            </svg>
                                        </div>
                                        Upload de arquivos Excel/CSV
                                    </li>
                                    <li className="flex items-center gap-2.5">
                                        <div className="w-5 h-5 rounded-full bg-primary-500/20 flex items-center justify-center group-hover:bg-primary-500/30 transition-colors">
                                            <svg className="w-3 h-3 text-primary-400" fill="currentColor" viewBox="0 0 20 20">
                                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                            </svg>
                                        </div>
                                        Chat com IA para insights
                                    </li>
                                    <li className="flex items-center gap-2.5">
                                        <div className="w-5 h-5 rounded-full bg-primary-500/20 flex items-center justify-center group-hover:bg-primary-500/30 transition-colors">
                                            <svg className="w-3 h-3 text-primary-400" fill="currentColor" viewBox="0 0 20 20">
                                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                            </svg>
                                        </div>
                                        Análise automatizada com ML
                                    </li>
                                </ul>

                                {/* CTA */}
                                <div className="relative flex items-center text-primary-400 font-semibold group-hover:translate-x-1 transition-transform duration-300">
                                    Começar agora
                                    <svg className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                                    </svg>
                                </div>
                            </button>

                            {/* Card 2: Classificação - Coming Soon */}
                            <div className="bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-6 relative overflow-hidden">
                                {/* Disabled Overlay */}
                                <div className="absolute inset-0 bg-primary-900/50 backdrop-blur-[1px] z-10" />

                                {/* Coming Soon Badge */}
                                <div className="absolute top-5 right-5 z-20">
                                    <span className="px-3 py-1.5 bg-white/20 text-white/80 text-xs font-medium rounded-full border border-white/10">
                                        Em breve
                                    </span>
                                </div>

                                {/* Icon */}
                                <div className="mb-4 inline-flex p-3 rounded-xl bg-white/10 shadow-lg">
                                    <svg
                                        xmlns="http://www.w3.org/2000/svg"
                                        fill="none"
                                        viewBox="0 0 24 24"
                                        strokeWidth={2}
                                        stroke="rgba(255,255,255,0.5)"
                                        className="w-6 h-6"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z"
                                        />
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            d="M6 6h.008v.008H6V6z"
                                        />
                                    </svg>
                                </div>

                                <h2 className="text-xl font-bold text-white/40 mb-2">
                                    Análises Avançadas
                                </h2>
                                <p className="text-white/30 leading-relaxed mb-5">
                                    Gere análises de Pareto, Top N e dashboards visuais dos seus dados
                                </p>

                                <ul className="text-sm text-white/25 space-y-2.5">
                                    <li className="flex items-center gap-2.5">
                                        <div className="w-5 h-5 rounded-full bg-white/10 flex items-center justify-center">
                                            <svg className="w-3 h-3 text-white/30" fill="currentColor" viewBox="0 0 20 20">
                                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                            </svg>
                                        </div>
                                        Análise de Pareto (ABC)
                                    </li>
                                    <li className="flex items-center gap-2.5">
                                        <div className="w-5 h-5 rounded-full bg-white/10 flex items-center justify-center">
                                            <svg className="w-3 h-3 text-white/30" fill="currentColor" viewBox="0 0 20 20">
                                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                            </svg>
                                        </div>
                                        Análises Top N (categorias, fornecedores, itens)
                                    </li>
                                    <li className="flex items-center gap-2.5">
                                        <div className="w-5 h-5 rounded-full bg-white/10 flex items-center justify-center">
                                            <svg className="w-3 h-3 text-white/30" fill="currentColor" viewBox="0 0 20 20">
                                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                            </svg>
                                        </div>
                                        Dashboards e gráficos interativos
                                    </li>
                                </ul>
                            </div>
                        </div>

                        {/* Footer */}
                        <div className="mt-8 text-center">
                            <div className="inline-flex items-center gap-3 px-5 py-2.5 bg-white/5 backdrop-blur-sm rounded-full border border-white/10">
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-primary-500 animate-pulse" />
                                    <span className="text-sm text-white/50">Powered by</span>
                                </div>
                                <span className="text-sm font-semibold text-white/70">Microsoft Copilot Studio</span>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </React.Fragment>
    )
}
