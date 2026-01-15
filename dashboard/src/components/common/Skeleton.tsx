import React from 'react';

/**
 * 骨架屏组件
 * 用于在数据加载时显示占位符
 */

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'rectangular' | 'circular';
  width?: string | number;
  height?: string | number;
  animation?: 'pulse' | 'wave' | 'none';
}

export function Skeleton({
  className = '',
  variant = 'text',
  width,
  height,
  animation = 'pulse'
}: SkeletonProps) {
  const getVariantClass = () => {
    switch (variant) {
      case 'circular':
        return 'rounded-full';
      case 'rectangular':
        return 'rounded-md';
      default:
        return 'rounded';
    }
  };

  const getAnimationClass = () => {
    switch (animation) {
      case 'wave':
        return 'animate-wave';
      case 'none':
        return '';
      default:
        return 'animate-pulse';
    }
  };

  const style: React.CSSProperties = {};
  if (width) style.width = typeof width === 'number' ? `${width}px` : width;
  if (height) style.height = typeof height === 'number' ? `${height}px` : height;

  return (
    <div
      className={`bg-gray-700 ${getVariantClass()} ${getAnimationClass()} ${className}`}
      style={style}
    />
  );
}

/**
 * 表格骨架屏
 */
export function TableSkeleton({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex gap-3">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton
              key={colIndex}
              variant="text"
              className="flex-1"
              height={40}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/**
 * 卡片骨架屏
 */
export function CardSkeleton() {
  return (
    <div className="bg-white/5 border border-white/10 rounded-lg p-6 space-y-4">
      <Skeleton variant="rectangular" height={32} width="60%" />
      <Skeleton variant="text" height={48} />
      <Skeleton variant="text" height={24} width="40%" />
    </div>
  );
}

/**
 * 列表骨架屏
 */
export function ListSkeleton({ items = 5 }: { items?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: items }).map((_, index) => (
        <div key={index} className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
          <Skeleton variant="circular" width={40} height={40} />
          <div className="flex-1 space-y-2">
            <Skeleton variant="text" height={20} width="60%" />
            <Skeleton variant="text" height={16} width="40%" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * 统计卡片骨架屏
 */
export function StatCardSkeleton() {
  return (
    <div className="bg-gradient-to-br from-gray-800/50 to-gray-900/50 border border-white/10 rounded-xl p-6 space-y-4">
      <Skeleton variant="text" height={20} width="40%" />
      <Skeleton variant="text" height={40} />
      <Skeleton variant="text" height={16} width="60%" />
    </div>
  );
}

/**
 * 图谱骨架屏
 */
export function GraphSkeleton() {
  return (
    <div className="w-full h-full bg-gray-900/50 flex items-center justify-center">
      <div className="text-center">
        <Skeleton variant="circular" width={80} height={80} className="mx-auto mb-4" />
        <Skeleton variant="text" height={24} width="200" className="mx-auto" />
      </div>
    </div>
  );
}
