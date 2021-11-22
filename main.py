
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import colorchooser

#format (Name, planes, bits,RGB)
#None=IDC
#descriptive names do not mean save
def generateAttributes(width, height, planes, bits_per_plane, isgrayscale=False,truncated_width=None):
    result = {}
    bpp = planes * bits_per_plane
    result["BPP"] = bpp
    result["Packed"] = planes < 2
    result["Grayscale"] = isgrayscale
    result["Indexed"] = bpp <= 8 and not (isgrayscale and bpp == 8)
    result["VGA Mode"] = None
    result["EGA Mode"] = None
    result["Planes"] = planes
    result["Bits per plane"] = bits_per_plane
    result["Colors"] = 2 ** bpp
    result["width"] = width
    result["height"] = height
    result["Bytes per row"] = (width * bits_per_plane + 7) // 8
    result["True Bytes per row"] = result["Bytes per row"] + (result["Bytes per row"] & 1)
    if bpp == 1:
        result["VGA Mode"] = 0x11
        result["EGA Mode"] = 0xf
    if planes == 1 and bits_per_plane == 2:
        result["VGA Mode"] = 4
        result["EGA Mode"] = 4
    if planes == 4 and bits_per_plane == 1:
        result["VGA Mode"] = 0x12
        result["EGA Mode"] = 0x10
    if planes == 1 and bits_per_plane == 8:
        result["VGA Mode"] = 0x13
    result["Plane Mask"] = ((2 ** 32) - 1) - (2 ** (32 - bits_per_plane) - 1)
    if (truncated_width==None):
        result["Truncated Width"]=width
    else:
        result["Truncated Width"]=truncated_width

    return result
class pcx_file():
    def __init__(self,width,height,planes,bits_per_plane):
        self.planes=planes
        self.bits_per_plane=bits_per_plane
        self.version=0xcc
        self.file=None
        self.width=width
        self.height=height
        self.isgrayscale=True
        self.palette=[]
        self.image_data=bytearray()
        self.truncated_width=width
        self.prev_attribute_call_value=self.getAttributes()

    def __init__(self,image_file):
        self.file=image_file
        image_file.seek(1,1)
        self.version=int.from_bytes(image_file.read(1),"little")
        image_file.seek(1,1)
        self.bits_per_plane=int.from_bytes(image_file.read(1),"little")

        #get width and height by subtracting the frame coordinates
        self.truncated_width=-int.from_bytes(image_file.read(2),"little")
        self.height=-int.from_bytes(image_file.read(2),"little")
        self.truncated_width+=int.from_bytes(image_file.read(2),"little")+1
        self.height+=int.from_bytes(image_file.read(2),"little")+1

        image_file.seek(4,1)
        palette_data=image_file.read(48)
        image_file.seek(1,1)
        self.planes=int.from_bytes(image_file.read(1),"little")
        tmp=int.from_bytes(image_file.read(2),"little")
        self.width=(tmp*8)//self.bits_per_plane
        image_file.seek(2,1)
        self.isgrayscale=image_file.read(2)==b'\x02\x00'
        attr=self.getAttributes()
        if (attr["Indexed"] and attr["Colors"]>16):
            extra=attr["Colors"]*3
            image_file.seek(-extra,2)
            image_data_size=image_file.tell()-1-128
            palette_data=image_file.read()
        else:
            image_file.seek(0,2)
            image_data_size=image_file.tell()-128
        if (attr["Indexed"]):
            self.generatePalette(palette_data)
        image_file.seek(128,0)
        image_data=image_file.read(image_data_size)
        self.generateImage(image_data)
    def getAttributes(self):
        self.prev_attribute_call_value=generateAttributes(self.width,self.height,self.planes,self.bits_per_plane,self.isgrayscale)
        return self.prev_attribute_call_value

    def generateImage(self,compressed_image_data):
        self.image_data=bytearray()
        i=0
        while (i<len(compressed_image_data)):
            if(compressed_image_data[i]>=192):
                for j in range(compressed_image_data[i]-192):
                    self.image_data.append(compressed_image_data[i+1])
                i+=2
            else:
                self.image_data.append(compressed_image_data[i])
                i+=1
    def compressImage(self):
        result=bytearray()
        i=0
        while (i<len(self.image_data)):
            pxcnt=1
            write_pxcnt=True
            px=self.image_data[i]
            if (i+2<len(self.image_data) and px==self.image_data[i+1]==self.image_data[i+2]):
                pxcnt=0
                while(i+pxcnt < len(self.image_data) and self.image_data[i+pxcnt]==px and pxcnt<63):
                    pxcnt+=1
            elif (px>=192):
                if (i+1<len(self.image_data)):
                    if( px==self.image_data[i+1]):
                        pxcnt=2
            else:
                write_pxcnt=False
            if (write_pxcnt):
                tmp=pxcnt+192
                result.append(tmp)
            result.append(px)
            i+=pxcnt
        return result

    def makeCanvas(self,parent,progress_bar=None):
        canvas=tk.Canvas(parent,width=self.truncated_width,height=self.height,bg='magenta')
        attr=self.getAttributes()

        for y in range(self.height):

            for x in range(self.truncated_width):
                b=self.get_pixel(x,y)
                if (attr["Indexed"]):
                    px=(self.palette[b][0]<<16)+(self.palette[b][1]<<8)+(self.palette[b][2])
                else:
                    bpc=attr["BPP"]//3
                    px=0
                    for i in range(3):
                        px<<=bpc
                        px+=b%(2**bpc)
                        b>>=bpc
                color="#"+format(px,"06x")
                canvas.create_rectangle(x+1,y+1,x+1,y+1,outline=color)

            if (progress_bar):
                progress_bar["value"]=(y/self.height)*100
                progress_bar.update()
        return canvas




    def saveImage(self,file):
        attr=self.getAttributes()
        file.write(b"\x0a\x05\x01")
        file.write(self.bits_per_plane.to_bytes(1,"little"))
        file.write(b"\x01\x00\x01\x00")
        file.write(self.width.to_bytes(2,"little"))
        file.write(self.height.to_bytes(2,"little"))
        file.write(b"\x2c\x01\x2c\x01")
        if attr["Indexed"]:
            if attr["Grayscale"]:
                for i in range(16):
                    file.write(self.palette[i][0].to_bytes(1, "little"))
            else:
                for i in range(16):
                    for j in range(3):
                        file.write(self.palette[i][j].to_bytes(1,"little"))
        else:
            tmp=0
            file.write(tmp.to_bytes(48,"little"))
        file.write(b"\x00")
        file.write(self.planes.to_bytes(1,"little"))
        file.write(attr["True Bytes per row"].to_bytes(2,"little"))
        if (self.isgrayscale):
            file.write(b"\x02\x00")
        else:
            file.write(b"\x01\x00")
        file.write(b"\x80\x07\x38\x04")
        tmp=0
        file.write(tmp.to_bytes(54,"little"))
        file.write(self.compressImage())
        if (attr["Indexed"] and attr["Colors"]>16):
            file.write(b"\x0c")
            if (attr["Grayscale"]):
                for i in range(768):
                    if (len(self.palette)<i):
                        file.write(self.palette[i][0].to_bytes(1,"little"))
                    else:
                        file.write(b"\x00")

            else:
                for i in range(256):
                    for j in range(3):
                        file.write(self.palette[i][j].to_bytes(1,"little"))


    def generatePalette(self,palette_data):
        self.palette=[]
        if (self.isgrayscale):
            for i in range(0,len(palette_data)):
                self.palette.append([palette_data[i],palette_data[i],palette_data[i]])
        else:
            for i in range(0,len(palette_data),3):
                self.palette.append([palette_data[i+0],palette_data[i+1],palette_data[i+2]])



    def get_pixel(self, x,y):
        b=0
        attr=self.prev_attribute_call_value
        bytesperrow=attr["True Bytes per row"]
        for i in range(self.planes):
            coarse_x=(x*self.bits_per_plane)//8
            fine_x=(x*self.bits_per_plane)%8
            index=y*bytesperrow*self.planes
            index+=i*bytesperrow
            index+=coarse_x
            buf=0
            for j in range(4):
                buf<<=8
                try:
                    buf+=self.image_data[index+j]
                except IndexError:
                    pass
            mask=attr["Plane Mask"]>>fine_x
            pln=buf&mask
            pln>>=32-fine_x-self.bits_per_plane
            b+=pln<<(i*self.bits_per_plane)
        return b
    def replane(self,new_plane_count,progress_bar=None):
        attr=self.getAttributes()
        new_bits_per_plane=attr["BPP"]//new_plane_count
        new_attr=generateAttributes(self.width,self.height,new_plane_count,new_bits_per_plane)
        bytesperrownew=new_attr["True Bytes per row"]
        new_image_data_array=bytearray(bytesperrownew*self.height*new_plane_count)
        for y in range(self.height):
            for x in range(self.truncated_width):
                b=self.get_pixel(x,y)
                mask=(1<<new_bits_per_plane)-1

                for i in range(new_plane_count):
                    coarse_x = (x * new_bits_per_plane) // 8
                    fine_x = (x * new_bits_per_plane) % 8
                    index = y * bytesperrownew * new_plane_count
                    index += i * bytesperrownew
                    index += coarse_x
                    #mask=(1<<(i*new_bits_per_plane+1))-1
                    #mask-=(1<<((i-1)*new_bits_per_plane+1))-1


                    pln=b&(mask<<(new_bits_per_plane*i))
                    pln>>=new_bits_per_plane*i
                    pln<<=8-fine_x-new_bits_per_plane

                    while(pln>0):
                        new_image_data_array[index]|=(pln%256)
                        pln>>=8
                        index+=1
            if (progress_bar):
                progress_bar["value"] = (y / self.height) * 100
                progress_bar.update()
        self.planes=new_plane_count
        self.bits_per_plane=new_bits_per_plane
        self.image_data=new_image_data_array
    def pad(self):
        attr=self.getAttributes()
        self.width=(attr["Bytes per row"]*8)//attr["Bits per plane"]
    def dump(self):
        file=open("dump.data","wt")
        cnt=0
        attr=self.getAttributes()
        for byte in self.image_data:
            file.write(format(byte,"02x"))
            file.write(" ")
            cnt+=1
            if(cnt>=attr["True Bytes per row"]):
                cnt=0
                file.write("\n")







class MainScreen():

    def __init__(self):
        self.screen = tk.Tk()
        self.button_frame=tk.Frame(self.screen)

        self.loadbutton=tk.Button(self.button_frame,text="Load",command=self.load_file_function)
        self.loadbutton.grid(column=0,row=0)
        self.savebutton=tk.Button(self.button_frame,text="Save",command=self.save_file_function,state=tk.DISABLED)
        self.savebutton.grid(column=1,row=0)
        self.refresh=tk.Button(self.button_frame,text="Refresh",command=self.update,state=tk.DISABLED)
        self.refresh.grid(column=2,row=0)
        self.dump=tk.Button(self.button_frame,text="Dump",command=self.dump)
        self.dump.grid(column=5,row=0)
        self.dump=tk.Button(self.button_frame,text="Pad",command=self.pad)
        self.dump.grid(column=6,row=0)
        #self.planes_entry=tk.Entry(self.button_frame, text="Planes", state=tk.DISABLED)
        #self.planes_entry.bind("<Return>",self.setBitplanes)
        #self.planes_entry.grid(column=4,row=0)
        self.planes_combobox=ttk.Combobox(self.button_frame,state=tk.DISABLED,values=[1,2,4,8])
        self.planes_combobox.bind("<<ComboboxSelected>>",self.setBitplanes)
        self.planes_combobox.grid(column=4,row=0)
        self.button_frame.grid(column=0,row=0)
        self.image_file=None
        self.image_instance=None
        self.attribute_label=tk.Label(self.screen)
        self.palette_combobox=None
        self.attribute_label.grid(column=0,row=2)
        self.palette_frame=tk.Frame(self.screen)
        self.palette_frame.grid(column=0,row=3)
        self.palette_combobox = ttk.Combobox(self.palette_frame, state=tk.DISABLED)
        self.palette_combobox.bind("<<ComboboxSelected>>", self.switch_palette)
        self.palette_button = tk.Button(self.palette_frame,command=self.set_palette, state=tk.DISABLED)
        self.palette_combobox.grid(column=0, row=0)
        self.palette_button.grid(column=1, row=0)

        self.progress_bar=ttk.Progressbar(self.screen,orient="horizontal",mode="determinate")
        self.canvas=tk.Canvas(self.screen,width=256,height=256,bg='magenta')
        self.canvas.grid(column=0,row=1)
        self.screen.mainloop()
    def pad(self):
        self.image_instance.pad()
        self.update()
    def dump(self):
        self.image_instance.dump()
    def setBitplanes(self,event):
        attr=self.image_instance.getAttributes()
        bpp=attr["BPP"]
        try:
            planes=int(self.planes_combobox.get())
            bits_per_plane=bpp/planes
            if (bits_per_plane == 0 or bits_per_plane%1!=0):
                return

        except ValueError:
            return
        self.progress_bar.grid(column=0, row=1)
        self.image_instance.replane(planes,self.progress_bar)
        self.progress_bar.grid_forget()
        self.update()


    def load_file_function(self):
        self.image_file = filedialog.askopenfile(filetypes=[("", "*.pcx")], mode='rb')
        if (self.image_file):
            self.image_instance = pcx_file(self.image_file)
            self.update()

    def save_file_function(self):
        self.image_file=filedialog.asksaveasfile(filetypes=[("", "*.pcx")], mode='wb')
        if (self.image_file):
            self.image_instance.saveImage(self.image_file)
            #self.update()
    def switch_palette(self,event):
        index=int(self.palette_combobox.get())
        clr=self.image_instance.palette[index][0]*65536+self.image_instance.palette[index][1]*256+self.image_instance.palette[index][2]
        self.palette_button["bg"]="#"+format(clr,"06x")
    def set_palette(self):
        colorraw=colorchooser.askcolor()

        self.palette_button["bg"] = colorraw[1]
        color=colorraw[0]
        index = int(self.palette_combobox.get())
        self.image_instance.palette[index]=list(color)
        self.update()


    def update(self):

        if(self.image_instance):
            text=""
            attrs=self.image_instance.getAttributes()
            for attr in  attrs:
                text+=attr+": "+str(attrs[attr])+"\n"
            self.attribute_label["text"]=text
            if (attrs["Indexed"]):
                self.palette_combobox["values"]=list(range(len(self.image_instance.palette)))
                self.palette_combobox["state"]="readonly"
                self.palette_button["state"]=tk.NORMAL
                self.planes_combobox["state"] = "readonly"
                self.planes_combobox.set(attrs["Planes"])
            else:
                self.palette_combobox["state"]=tk.DISABLED
                self.palette_button["state"]=tk.DISABLED
                self.planes_combobox["state"]=tk.DISABLED
                self.planes_combobox.set(attrs["Planes"])
            self.savebutton["state"]=tk.NORMAL
            self.refresh["state"]=tk.NORMAL

        if (self.canvas):
            self.canvas.destroy()
        self.progress_bar.grid(column=0, row=1)
        self.canvas = self.image_instance.makeCanvas(self.screen,self.progress_bar)
        self.progress_bar.grid_forget()
        self.canvas.grid(column=0, row=1)


if __name__=="__main__":
    s=MainScreen()
