"""
    自用小工具
    Author: 王勇涛
"""
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import sys
import getopt
import optparse
import time
import re
import os
import zipfile
from datetime import datetime
import shutil
from multiprocessing import Process
import psutil
from email import encoders
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
import smtplib


def doc():
    print('''
    ------------------------------------------------
            帮助文档
    自动部署      |
        -a, --deploy 开启自动部署
        -d, --dir    被监控的目录
        -b, --backup 被监控目录的原本文件被打包后存放的目录
    服务器负载警告 |
        -r, --report 开启服务器负载警告
        --momory     内存占用百分比警告(默认90%)
        --cpu        cpu 占用百分比警告(默认80%)
    ''')
    exit()


# 被监控的目录
path = r''
# 被监控目录的原本文件被打包后存放的目录
backupPath = r''



def iszip(newfile):
    if re.match(r'(.*-auto.zip)', newfile):
        return newfile
    else:
        return 'not'


def deploy(zipFilePath):
    """
    解压 -auto.zip 为后缀的压缩包，并将其移动到当前用户家目录下
    :param zipFilePath: 目标压缩包绝对路径
    :return: None
    """
    with zipfile.ZipFile(zipFilePath, 'r') as newZip:
        newZip.extractall(path=path)
    shutil.move(zipFilePath, os.path.join(os.path.expanduser('~'), os.path.split(zipFilePath)[1]))


def deleteOld(path, withoutReruler):
    dir = os.listdir(path)
    for file in dir:
        if not re.match(withoutReruler, file):
            if os.path.isdir(os.path.join(path, file)):
                shutil.rmtree(os.path.join(path, file), )
            else:
                os.remove(os.path.join(path, file))


def dumpOld(path, out2path):
    """
    将目录中原来的非 -auto.zip 结尾的文件打包
    :param path: 被监控的目录
    :param out2path: 打包后存放的目录
    :return: None
    """
    oldFiles = []
    oldDirs = []
    zip = zipfile.ZipFile(out2path, 'w', allowZip64=True)
    reruler = r'.*-auto.zip'
    for file in os.listdir(path):
        if not re.match(reruler, file):
            # 如果目标不是目录
            if not os.path.isdir(os.path.join(path, file)):
                oldFiles.append(os.path.join(path, file))

            # 如果目标是目录
            else:
                for dir, subdirs, files in os.walk(os.path.join(path, file)):
                    for fileItem in files:
                        oldDirs.append(os.path.join(dir, fileItem))
                    for dirItem in subdirs:
                        oldDirs.append(os.path.join(dir, dirItem))
                    for i in oldDirs:
                        zip.write(i, os.path.join(file, os.path.split(i)[1]))
    for file in oldFiles:
        zip.write(file, os.path.split(file)[1], zipfile.ZIP_DEFLATED)
    zip.close()
    # 删除被打包完的文件
    deleteOld(path, reruler)


def autoDeploy(eventsrc_path):
    """
    自动部署
    :param eventsrc_path:填写事件路径event.src_path
    :return:
    """
    if iszip(eventsrc_path) != 'not':
        oldProjCompressPath = os.path.join(backupPath, datetime.now().strftime('%Y-%m-%d-%H-%M-%S') + '.zip')
        dumpOld(path, oldProjCompressPath)
        time.sleep(3)
        deploy(eventsrc_path)


class Handler1(FileSystemEventHandler):
    def on_modified(self, event):
        pass

    def on_created(self, event):
        autoDeploy(event.src_path)

    def on_moved(self, event):
        autoDeploy(event.src_path)

    def on_closed(self, event):
        pass

    def on_deleted(self, event):
        pass


def Handler_start():
    event_handler = Handler1()
    obs = Observer()
    obs.schedule(event_handler, path, recursive=False)
    obs.start()
    try:
        while True:
            time.sleep(1)
    finally:
        obs.stop()
        obs.join()


def iscpuoverload():
    if psutil.cpu_percent() > 80:
        c = 0
        for i in range(10):
            time.sleep(1)
            if psutil.cpu_percent() > 80:
                c = c + 1
        if c >= 7:
            return 'is'


def ismemoryoverload():
    if psutil.swap_memory()[3] > 90:
        c = 0
        for i in range(10):
            time.sleep(1)
            if psutil.swap_memory()[3] > 90:
                c = c + 1
        if c >= 7:
            return 'is'


def _format_addr(s):
    """格式化邮件地址，不能简单地传入`name <addr@example.com>`，因为如果包含中文，需要通过`Header`对象进行编码。"""
    name, addr = parseaddr(s)
    return formataddr((Header(name, 'utf-8').encode(), addr))


def mail2admin(from_addr: str, password: str, to_addr: str, text: str):
    """
    发送邮件给管理员
    :param from_addr: 发送方邮件地址
    :param password: 发送方邮箱密码
    :param to_addr: 目标邮箱地址
    :param text: 邮件内容，文本格式
    """
    msg = MIMEText(text, 'plain', 'utf-8')
    msg['From'] = _format_addr('服务器告警 <%s>' % from_addr)
    msg['To'] = _format_addr('管理员 <%s>' % to_addr)
    msg['Subject'] = Header('服务器告警', 'utf-8').encode()
    # 输入SMTP服务器地址:
    smtp_server = 'smtp.qq.com'
    smtp_port = 465
    server = smtplib.SMTP_SSL(smtp_server, smtp_port)
    # server.set_debuglevel(1)
    server.login(from_addr, password)
    server.sendmail(from_addr, [to_addr], msg.as_string())
    server.quit()


def report():
    while True:
        if iscpuoverload() and ismemoryoverload():
            text = '''
                        cpu 使用率大于 80% 连续 10 秒！！！
                        内存占用率大于 90% 连续 10 秒！！！
                   '''
            mail2admin('wangyongtao2000@qq.com', 'mxtsyhepwgeobbaf', 'wangyongtao2000@qq.com', text)
            time.sleep(3600)
            continue
        if iscpuoverload():
            text = 'cpu 使用率大于 80% 连续 10 秒！！！'
            mail2admin('wangyongtao2000@qq.com', 'mxtsyhepwgeobbaf', 'wangyongtao2000@qq.com', text)
            time.sleep(3600)
            continue
        elif ismemoryoverload():
            text = '内存占用率大于 90% 连续 10 秒！！！'
            mail2admin('wangyongtao2000@qq.com', 'mxtsyhepwgeobbaf', 'wangyongtao2000@qq.com', text)
            time.sleep(3600)
            continue
        else:
            continue


if __name__ == '__main__':
    p1 = Process(target=Handler_start)
    p2 = Process(target=report)
    p1.start()
    # p1.join()
    p2.start()
