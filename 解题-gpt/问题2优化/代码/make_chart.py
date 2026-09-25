from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
HERE=Path(__file__).resolve(); OUT=HERE.parents[1]/'图表'; OUT.mkdir(parents=True,exist_ok=True)
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','Arial']
plt.rcParams['axes.unicode_minus']=False
labels=['系统完成时间','总运输能耗','架次']
units=['min','kWh','架']
base=[173.7274,95.2042,43]; opt=[164.8136,95.2042,43]
COLORS={'baseline':'#598EBB','candidate':'#8CCDC6'}  # ocean-mint palette
fig,axs=plt.subplots(1,3,figsize=(10.2,4.5),dpi=220)
for i,ax in enumerate(axs):
    bars=ax.bar(['正式基线','ALNS候选'],[base[i],opt[i]],color=[COLORS['baseline'],COLORS['candidate']],edgecolor='#4A4A4A',linewidth=.8,width=.62)
    pad=max(base[i]*.045,.5); ax.set_ylim(0,max(base[i],opt[i])+pad*3.0)
    ax.set_title(labels[i],fontsize=12); ax.set_ylabel(units[i]); ax.grid(axis='y',alpha=.22,linewidth=.7); ax.set_axisbelow(True)
    ax.tick_params(axis='x',labelrotation=18)
    for bar in bars: ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+pad*.25,f'{bar.get_height():.4g}',ha='center',va='bottom',fontsize=9)
axs[0].text(.02,-.28,'80箱全部按时；官方 DEM、机队和电池约束均通过',transform=axs[0].transAxes,fontsize=9,color='#425466')
fig.suptitle('问题二：官方数据下的调度顺序优化',fontsize=15,y=.99)
fig.tight_layout(rect=[0,0.08,1,0.95]); fig.savefig(OUT/'问题二_ALNS基线对比.png',bbox_inches='tight'); plt.close(fig)
