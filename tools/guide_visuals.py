"""Diagrams with explicit actor, state, action and mechanism labels."""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont

COLORS={'A':'#236a92','S':'#af6333','H':'#2d8068','M':'#596773','X':'#6a5790'}
NAMES={'A':'AGENT','S':'TRẠNG THÁI','H':'HÀNH ĐỘNG','M':'CƠ CHẾ','X':'NGOẠI SINH'}
INK='#142536'; GRAY='#596773'
def font(size,bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',size)
def txt(d,xy,value,size=34,color=INK,bold=False,anchor='ma'):
    d.multiline_text(xy,value,font=font(size,bold),fill=color,spacing=8,align='center',anchor=anchor)
def box(d,rect,kind,title,body='',ts=36,bs=33):
    x1,y1,x2,y2=rect; col=COLORS[kind]
    d.rounded_rectangle(rect,20,fill='#f5f7f9',outline=col,width=4)
    txt(d,((x1+x2)/2,y1+14),kind+'  '+NAMES[kind],26,col,True)
    txt(d,((x1+x2)/2,y1+57),title,ts,INK,True)
    if body:txt(d,((x1+x2)/2,y1+112),body,bs)
def arrow(d,a,b,kind='H',label=None,xy=None,info=False):
    col=COLORS['M'] if info else COLORS[kind]
    distance=math.dist(a,b)
    if info:
        for start in range(0,int(distance),25):
            end=min(start+14,distance)
            d.line([(a[0]+(b[0]-a[0])*start/distance,a[1]+(b[1]-a[1])*start/distance),(a[0]+(b[0]-a[0])*end/distance,a[1]+(b[1]-a[1])*end/distance)],fill=col,width=5)
    else:d.line([a,b],fill=col,width=6)
    theta=math.atan2(b[1]-a[1],b[0]-a[0]);head=22
    d.polygon([b,(b[0]-head*math.cos(theta-.45),b[1]-head*math.sin(theta-.45)),(b[0]-head*math.cos(theta+.45),b[1]-head*math.sin(theta+.45))],fill=col)
    if label:txt(d,xy,label,30,col)
def canvas(height):
    im=Image.new('RGB',(1600,height),'white');return im,ImageDraw.Draw(im)
def save(im,d,work,name):
    y=im.height-100
    txt(d,(800,y),'A Agent   S Trạng thái   H Hành động   M Cơ chế   X Ngoại sinh',28,GRAY)
    txt(d,(800,y+44),'Nét đứt: thông tin hoặc ảnh hưởng • Nét liền: thao tác hoặc dòng tài sản',26,GRAY)
    path=work/(name+'.png');im.save(path,dpi=(240,240));return path

def build_diagrams(work:Path):
    fig={}
    im,d=canvas(930)
    txt(d,(800,20),'Agent hành động rồi đọc lại trạng thái mới',44,INK,True)
    box(d,(20,130,470,370),'A','Người gửi Anchor','Quan sát rồi yêu cầu rút\nvà bán UST đã nhận')
    box(d,(580,130,1030,370),'S','Giá UST','USD cho 1 UST\nThay đổi sau mua bán')
    box(d,(1140,130,1580,370),'A','Arbitrageurs','Mua UST rẻ\nđổi rồi bán LUNA')
    arrow(d,(470,250),(580,250),label='H Rút bán',xy=(525,395))
    arrow(d,(1030,250),(1140,250),info=True)
    box(d,(580,525,1030,760),'S','Giá và cung LUNA','USD cho 1 LUNA\nSố token đang tồn tại',bs=32)
    arrow(d,(1360,370),(1360,650));arrow(d,(1360,650),(1030,650),label='H Đổi và bán',xy=(1285,720))
    arrow(d,(580,650),(245,650),info=True);arrow(d,(245,650),(245,370),info=True)
    txt(d,(330,705),'Giá mới ảnh hưởng\nquyết định tiếp theo',30,GRAY)
    fig['map']=save(im,d,work,'01_he_thong')

    im,d=canvas(1080)
    entries=[('A','Ai hành động','Người gửi i\nCó số dư và quy tắc riêng'),('S','Đang ở tình trạng nào','Ví i có 200 UST\nGiá UST là 0,90 USD'),('H','Làm gì trong bước này','Người gửi bán 100 UST\nDòng chuyển có đơn vị UST'),('M','Luật xử lý thế nào','Anchor phục vụ rút\ncadCAD chạy đúng thứ tự'),('X','Đầu vào từ ngoài','Giá BTC quan sát\nLịch khả dụng của quỹ')]
    positions=[(20,20),(840,20),(20,325),(840,325),(430,630)]
    for (kind,title,body),(x,y) in zip(entries,positions):box(d,(x,y,x+740,y+260),kind,title,body,bs=34)
    fig['types']=save(im,d,work,'09_phan_loai')

    im,d=canvas(1040)
    entries=[('A','Người gửi đại diện','1.000 dòng có trọng số\nQuyền đòi và ví riêng\nQuyết định yêu cầu rút'),('A','Người gửi tổ chức','Phần tiền gửi còn lại\nMột nhóm mô tả gộp\nRút theo tỷ lệ kỳ vọng'),('A','Arbitrageurs','20 tác nhân chung luật\nCó USD và LUNA riêng\nGiao dịch nếu có lời'),('M','Anchor và native','Bộ phận vận hành\nThu nợ trả lãi trả UST\nĐốt UST phát hành LUNA'),('A','Bên mua tổng hợp','Đối ứng và bên ngoài\nCó vốn và token hữu hạn\nKhông là sàn đầy đủ'),('A','LFG và TFL','Tác nhân hỗ trợ theo lịch\nVốn chỉ dùng khi khả dụng\nHành vi có điều kiện')]
    for i,(kind,title,body) in enumerate(entries):
        x=20+(i%3)*530;y=15+(i//3)*455
        box(d,(x,y,x+500,y+410),kind,title,body,ts=33,bs=32)
    fig['agents']=save(im,d,work,'02_cac_thanh_phan')

    im,d=canvas(1060)
    box(d,(20,20,630,290),'S','Thông tin được quan sát','Giá UST LUNA • tỷ lệ rút\nTỷ lệ hàng đợi\nCó độ trễ theo người gửi')
    box(d,(970,20,1580,290),'A','Người gửi i','Quy tắc rút tính xác suất\nH Gửi yêu cầu rút')
    arrow(d,(630,160),(970,160),info=True)
    box(d,(970,420,1580,690),'S','Hàng đợi rút của i','Số UST đã yêu cầu\nnhưng chưa được phục vụ')
    arrow(d,(1275,290),(1275,420),label='H Thêm yêu cầu',xy=(1420,340))
    box(d,(20,420,630,690),'M','Anchor phục vụ','Đọc S Tiền mặt và cờ mở\nH Chuyển UST nếu đủ tiền\nS Hàng đợi giảm khi đã trả',bs=31)
    arrow(d,(970,545),(630,545),info=True,label='Đọc nghĩa vụ',xy=(800,590))
    box(d,(420,770,1190,930),'S','UST trong ví của i','Tăng khi nhận được tiền • H Bán sau đó',ts=34,bs=30)
    arrow(d,(325,690),(325,850));arrow(d,(325,850),(420,850))
    fig['withdraw']=save(im,d,work,'03_quyet_dinh_rut')

    im,d=canvas(1130)
    txt(d,(800,15),'A Arbitrageur thực hiện chuỗi giao dịch dưới đây',38,COLORS['A'],True)
    box(d,(30,100,500,355),'H','1 Mua UST','Mua 100 UST giá 0,90\nS USD ví giảm 90 USD',ts=36)
    box(d,(565,100,1035,355),'M','2 Native swap','H Đốt 100 UST\nH Phát hành 10 LUNA')
    box(d,(1100,100,1570,355),'S','3 Số dư sau phí','9,6 LUNA vào ví agent\n0,4 LUNA vào tài khoản phí',bs=31)
    arrow(d,(500,225),(565,225));arrow(d,(1035,225),(1100,225))
    txt(d,(800,415),'S Oracle LUNA trong ví dụ là 10 USD cho 1 LUNA',34,COLORS['S'])
    box(d,(1100,530,1570,770),'H','4 Bán LUNA','Bán 9,6 giá bình quân 9,80\nS USD ví tăng 94,08 USD',bs=31)
    arrow(d,(1335,355),(1335,530))
    box(d,(30,530,1035,770),'M','Kiểm trước khi bắt đầu giao dịch','Quote: 94,08 − 90 = 4,08 USD trước phí bán\nChỉ bắt đầu nếu còn có lời sau mọi phí',ts=34,bs=33)
    arrow(d,(1100,650),(1035,650),info=True)
    txt(d,(800,825),'S Tổng cung UST giảm 100 • S Tổng cung LUNA tăng 10',36,COLORS['S'],True)
    txt(d,(800,920),'Ví dụ minh họa cơ chế • Không phải giao dịch lịch sử',32,GRAY)
    fig['arb']=save(im,d,work,'04_arbitrage')

    im,d=canvas(1050)
    box(d,(20,30,510,305),'S','Tiền mặt Anchor','UST thật đang có\nđể phục vụ rút')
    box(d,(600,30,1110,305),'S','UST trong ví người gửi','Token đã nhận được\nAgent sở hữu số dư này',ts=33)
    box(d,(1220,30,1580,305),'S','Kho bên mua','USD và UST\nđều hữu hạn',ts=34)
    arrow(d,(510,145),(600,145),label='H Rút',xy=(555,75))
    arrow(d,(600,250),(510,250),label='H Gửi lại',xy=(555,335))
    arrow(d,(1110,180),(1220,180),label='H Bán UST',xy=(1165,335))
    box(d,(20,480,710,785),'S','Tổng cung UST','Tổng token UST còn tồn tại\nChuyển ví không đổi tổng cung\nNative burn làm giảm tổng cung',bs=33)
    box(d,(890,480,1580,785),'S','Tổng cung LUNA','Tổng token LUNA còn tồn tại\nNative mint làm tăng tổng cung\nLUNA của agent và phí đều được tính',bs=32)
    arrow(d,(710,630),(890,630),label='H Native',xy=(800,565))
    txt(d,(800,830),'M Native đổi cơ cấu token • Không phải chuyển cùng một token',32,GRAY)
    fig['stocks']=save(im,d,work,'05_ton_luong_dong_chay')

    im,d=canvas(1130)
    box(d,(40,40,590,300),'S','Giá UST giảm','USD cho 1 UST thấp hơn')
    box(d,(1010,40,1560,300),'H','Rút và bán UST','A Người gửi quyết định\nS Áp lực bán tăng')
    box(d,(1010,630,1560,900),'H','Đổi native và bán','A Arbitrageur giao dịch\nS Cung LUNA tăng\nS Giá LUNA có thể giảm',ts=34,bs=32)
    box(d,(40,630,590,900),'S','Tín hiệu tin cậy giảm','Tính từ giá và cung LUNA\nvà tổng cung UST\nTác động giá và hành vi',ts=34,bs=32)
    arrow(d,(590,170),(1010,170),info=True)
    arrow(d,(1285,300),(1285,630),info=True,label='Có lời mới đổi',xy=(1420,450))
    arrow(d,(1010,760),(590,760),info=True)
    arrow(d,(315,630),(315,300),info=True,label='Ảnh hưởng',xy=(140,450))
    txt(d,(800,365),'A Bên mua ngoài và LFG TFL',34,COLORS['A'],True)
    txt(d,(800,430),'H Mua UST có thể giảm áp lực',32,COLORS['H'])
    txt(d,(800,495),'S Vốn khả dụng giới hạn quy mô',32,COLORS['S'])
    txt(d,(800,960),'Đây là vòng ảnh hưởng • Không phải sơ đồ chuyển toàn bộ tiền',32,GRAY)
    fig['feedback']=save(im,d,work,'06_vong_phan_hoi')

    im,d=canvas(1090)
    entries=[('1 Quan sát','Đọc S và X Giá BTC\nCập nhật thời gian và cờ'),('2 Cứu trợ lịch sử','A LFG TFL theo lịch\nH Mua bằng vốn khả dụng'),('3 Agent quyết định','A Người gửi tính yêu cầu\nS Hàng đợi được cập nhật'),('4 Anchor phục vụ','H Thu nợ trả lãi trả UST\nS Tiền mặt quyền đòi đổi'),('5 Thị trường native','H Mua bán đốt phát hành\nS Giá và cung được cập nhật'),('6 Kiểm sổ tài sản','Kiểm toàn bộ S trong book\nLưu cho bước tiếp theo')]
    pos=[(20,15),(550,15),(1080,15),(1080,520),(550,520),(20,520)]
    for (title,body),(x,y) in zip(entries,pos):box(d,(x,y,x+500,y+330),'M',title,body,ts=33,bs=32)
    for a,b in [((520,180),(550,180)),((1050,180),(1080,180)),((1330,345),(1330,520)),((1080,685),(1050,685)),((550,685),(520,685))]:arrow(d,a,b)
    txt(d,(800,415),'M cadCAD điều phối • 15 phút mỗi bước ngoài',38,INK,True)
    txt(d,(800,910),'Bước 5 xử lý từng phút • cadCAD không phải một agent kinh tế',32,GRAY)
    fig['clock']=save(im,d,work,'07_thu_tu_buoc')

    im,d=canvas(950)
    box(d,(20,40,700,315),'S','Trước khi phục vụ rút','Quyền đòi i 1.000 UST\nVí i 0 UST • Hàng đợi i 200 UST\nAnchor có tiền và đang mở',bs=34)
    box(d,(900,40,1580,315),'A','Người gửi i','Đã gửi yêu cầu 200 UST\nKhông tự tạo token khi yêu cầu\nChờ M Anchor phục vụ',bs=33)
    arrow(d,(900,180),(700,180),info=True)
    box(d,(430,405,1170,645),'M','Anchor phục vụ đủ 200 UST','H Chuyển 200 UST sang ví i\nS Tiền mặt Anchor giảm 200 UST',bs=34)
    arrow(d,(350,315),(350,525));arrow(d,(350,525),(430,525))
    txt(d,(800,700),'S Sau khi trả: quyền đòi 800 • ví 200 • hàng đợi 0 UST',36,COLORS['S'],True)
    txt(d,(800,770),'S Tổng cung UST giữ nguyên • Không có token mới được phát hành',31,GRAY)
    fig['example']=save(im,d,work,'10_vi_du_trang_thai')
    return fig
