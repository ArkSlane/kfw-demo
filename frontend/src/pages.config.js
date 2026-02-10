import Requirements from './pages/Requirements';
import TestCases from './pages/TestCases';
import Automations from './pages/Automations';
import Releases from './pages/Releases';
import TestPlan from './pages/TestPlan';
import Executions from './pages/Executions';
import AIInsights from './pages/AIInsights';
import ToabRkIa from './pages/ToabRkIa';
import TestcaseMigration from './pages/TestcaseMigration';
import Admin from './pages/Admin';
import Layout from './Layout.jsx';


export const PAGES = {
    "Requirements": Requirements,
    "TestCases": TestCases,
    "Automations": Automations,
    "Releases": Releases,
    "TestPlan": TestPlan,
    "Executions": Executions,
    "AIInsights": AIInsights,
    "toab-rk-ia": ToabRkIa,
    "testcase-migration": TestcaseMigration,
    "admin": Admin,
}

export const pagesConfig = {
    mainPage: "TestPlan",
    Pages: PAGES,
    Layout: Layout,
};