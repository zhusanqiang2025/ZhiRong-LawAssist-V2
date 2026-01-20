import React, { useState } from 'react';
import { Card, Input, Button, Typography } from 'antd';
import { MessageOutlined } from '@ant-design/icons';
import './ChatWindow.css'; // <-- 添加这一行来引入样式

const { TextArea } = Input;
const { Paragraph } = Typography;

interface ChatWindowProps {
    isSending: boolean;
    onSendMessage: (message: string) => void;
}

const ChatWindow: React.FC<ChatWindowProps> = ({ isSending, onSendMessage }) => {
    const [message, setMessage] = useState('');

    const handleSend = () => {
        if (!message.trim()) return;
        onSendMessage(message);
        setMessage('');
    };

    return (
        <Card title="多轮交互修改" size="small" className="chat-card">
            <Paragraph>
                如果您对初稿不满意，请在下方输入修改意见，AI将实时更新文书内容。
            </Paragraph>
            <TextArea 
                rows={4} 
                placeholder="例如：请将甲方更改为“XXX公司”，并增加一条关于保密责任的条款。" 
                value={message}
                onChange={(e) => setMessage(e.target.value)}
            />
            <Button
                type="primary"
                icon={<MessageOutlined />}
                loading={isSending}
                onClick={handleSend}
                style={{ marginTop: 16 }}
                block
            >
                发送修改意见
            </Button>
        </Card>
    );
};

export default ChatWindow;
