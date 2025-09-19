import { Layout, Menu, Typography } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import TimezoneSelector from "./TimezoneSelector";

const { Header, Content, Footer } = Layout;

const menuItems = [
  { key: "/", label: "仪表盘" },
  { key: "/trades", label: "交易记录" },
  { key: "/calendar", label: "交易日历" },
  { key: "/imports", label: "数据导入" }
];

const AppLayout = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const activeKey = menuItems.find((item) =>
    item.key === "/" ? location.pathname === "/" : location.pathname.startsWith(item.key)
  )?.key ?? "/";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <Typography.Title level={4} style={{ color: "#fff", margin: 0 }}>
          交易日志
        </Typography.Title>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[activeKey]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ flex: 1 }}
        />
        <TimezoneSelector />
      </Header>
      <Content style={{ padding: "24px" }}>
        <Outlet />
      </Content>
      <Footer style={{ textAlign: "center" }}>Trade Journal © {new Date().getFullYear()}</Footer>
    </Layout>
  );
};

export default AppLayout;
